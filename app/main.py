"""Streamlit entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure project root is on Python path (needed for Streamlit Cloud)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Costa Rica timezone (UTC-6)
CR_TZ = timezone(timedelta(hours=-6))

import streamlit as st

from interfaces.streamlit.pages import dashboard, exports, inteligencia_comercial, search
from interfaces.streamlit.services import build_services


# ── Playwright browser install (Streamlit Cloud) ──────────────────────
# Streamlit Cloud has no build step, so we install Chromium at cold start.
# Only runs once per deploy via st.cache_resource.
MOCK_MODE = os.getenv("SAP_MOCK_MODE", "true").lower() == "true"

if not MOCK_MODE:

    @st.cache_resource(show_spinner="Instalando Chromium para SAP...")
    def _install_playwright() -> bool:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                st.warning(f"Chromium no se pudo instalar (código {result.returncode}). La app funcionará en modo simulación.")
                return False
            return True
        except Exception as exc:
            st.warning(f"Error instalando Chromium: {exc}. Modo simulación activado.")
            return False

    if not _install_playwright():
        os.environ["SAP_MOCK_MODE"] = "true"
# ─────────────────────────────────────────────────────────────────────


st.set_page_config(page_title="SAP B1 — Biomédico", layout="wide")

# -- Load CSS style --
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.markdown('<h1 class="title-gradient">SAP Business One — Biomédico</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle-desc">Query Manager Automation & Analytics Dashboard</p>', unsafe_allow_html=True)

services = build_services()
settings = services["settings"]
is_live = not settings.sap_mock_mode

# -- Sidebar navigation --
with st.sidebar:
    page = st.radio("Navegar", ["📊 Dashboard", "📈 Inteligencia Comercial", "🔍 Buscador", "📥 Exportar"])

    st.divider()
    st.markdown("### 📊 Estado")

    # Connection status
    badge_class = "live" if is_live else "mock"
    badge_label = "LIVE SAP" if is_live else "MOCK"
    st.markdown(f'<div class="status-badge {badge_class}">Modo: {badge_label}</div>', unsafe_allow_html=True)
    st.write("") # Spacer


    # Timestamp
    now = datetime.now(CR_TZ)
    st.caption(f"🕐 {now.strftime('%d/%m %H:%M')} CR (UTC-6)")

    # Datasets loaded
    datasets = {
        "df_correctivas": "Correctivas",
        "df_garantias": "Garantías",
        "df_pipeline_comercial": "Pipeline",
    }
    loaded = []
    for key, name in datasets.items():
        df = st.session_state.get(key)
        if df is not None and not df.empty:
            loaded.append(f"• {name} ({len(df)} filas)")
    
    # Also check commercial intelligence cache
    for key in st.session_state:
        if key.startswith("df_intel_comercial"):
            intel_df = st.session_state.get(key)
            if isinstance(intel_df, dict) and intel_df.get("data") is not None:
                loaded.append(f"• Intel. Comercial ({len(intel_df['data'])} filas)")

    if loaded:
        st.caption("📋 Datasets:\n" + "\n".join(loaded))
    else:
        st.caption("📋 Sin datos — usá el Dashboard o Inteligencia Comercial")

# -- Main content --
if page == "📊 Dashboard":
    dashboard.render(services)
elif page == "📈 Inteligencia Comercial":
    inteligencia_comercial.render(services)
elif page == "🔍 Buscador":
    search.render(services)
else:
    exports.render(services)