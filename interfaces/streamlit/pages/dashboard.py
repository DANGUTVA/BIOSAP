"""Unified Dashboard — KPIs + Pipeline Comercial."""

from __future__ import annotations

import pandas as pd
import streamlit as st


# -- Resumen ejecutivo arriba, Pipeline abajo. --

PIPELINE_STAGES = ["Oportunidad Venta", "En Garantía", "Otro"]
STAGE_ICONS = {"Oportunidad Venta": "🔴", "En Garantía": "🟢", "Otro": "⚪"}


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def _derive_pipeline_stage(df: pd.DataFrame) -> pd.DataFrame:
    col_estado = _find_column(df, ["estado", "contrato", "warranty"])
    if col_estado is None:
        return df
    df = df.copy()
    df["Etapa Pipeline"] = "Otro"
    df.loc[df[col_estado] == "Sin_Contrato", "Etapa Pipeline"] = "Oportunidad Venta"
    mask = df[col_estado].astype(str).str.contains("Garant", case=False, na=False)
    df.loc[mask, "Etapa Pipeline"] = "En Garantía"
    return df


# -- Data loading (cached in session_state) --


def _load_correctivas(services: dict) -> pd.DataFrame | None:
    key = "df_correctivas"
    if key not in st.session_state:
        with st.spinner("Cargando llamadas correctivas..."):
            try:
                res = services["pipeline"].execute(
                    query_id="llamadas_correctivas_division",
                    correlation_id="dashboard-correctivas",
                )
                st.session_state[key] = res["data"]
            except Exception as exc:
                st.error(f"Error correctivas: {exc}")
                st.session_state[key] = None
    return st.session_state.get(key)


def _load_garantias(services: dict) -> pd.DataFrame | None:
    key = "df_garantias"
    if key not in st.session_state:
        with st.spinner("Cargando garantías..."):
            try:
                res = services["pipeline"].execute(
                    query_id="garantias_90_dias",
                    correlation_id="dashboard-garantias",
                )
                st.session_state[key] = res["data"]
            except Exception as exc:
                st.error(f"Error garantías: {exc}")
                st.session_state[key] = None
    return st.session_state.get(key)


def _load_comercial(services: dict) -> pd.DataFrame | None:
    key = "df_pipeline_comercial"
    if key not in st.session_state:
        with st.spinner("Cargando pipeline comercial..."):
            try:
                res = services["pipeline"].execute(
                    query_id="pipeline_comercial",
                    correlation_id="dashboard-comercial",
                )
                st.session_state[key] = res["data"]
            except Exception as exc:
                st.error(f"Error pipeline comercial: {exc}")
                st.session_state[key] = None
    return st.session_state.get(key)


# -- Color helpers --


def _severity(value: int, *, warn: int = 10, danger: int = 20) -> str:
    if value >= danger:
        return "danger"
    if value >= warn:
        return "warn"
    return "ok"


def _metric_card(col, label: str, value, *, severity: str = "ok", delta: str = "") -> None:
    """Render a metric inside a colored card with border."""
    severity_class = f"metric-{severity}"
    
    # Map label prefix icons
    icon = ""
    if "correctivas" in label.lower() or "🔧" in label:
        icon = "🔧 "
        label = label.replace("🔧", "").strip()
    elif "equipos" in label.lower() or "🏥" in label:
        icon = "🏥 "
        label = label.replace("🏥", "").strip()
    elif "clientes" in label.lower() or "👥" in label:
        icon = "👥 "
        label = label.replace("👥", "").strip()
    elif "garantías" in label.lower() or "⏳" in label:
        icon = "⏳ "
        label = label.replace("⏳", "").strip()
    elif "prom" in label.lower() or "📅" in label:
        icon = "📅 "
        label = label.replace("📅", "").strip()
    elif "críticas" in label.lower() or "🚨" in label:
        icon = "🚨 "
        label = label.replace("🚨", "").strip()
    elif "oportunidad" in label.lower() or "🔴" in label:
        icon = "🔴 "
        label = label.replace("🔴", "").strip()
    elif "garantía" in label.lower() or "🟢" in label:
        icon = "🟢 "
        label = label.replace("🟢", "").strip()
    elif "otro" in label.lower() or "⚪" in label:
        icon = "⚪ "
        label = label.replace("⚪", "").strip()
        
    delta_html = f'<div class="metric-card-delta">{delta}</div>' if delta else ""
    
    card_html = f"""
    <div class="metric-card {severity_class}">
        <div class="metric-card-title">{icon}{label}</div>
        <div class="metric-card-value">{value}</div>
        {delta_html}
    </div>
    """
    with col:
        st.markdown(card_html, unsafe_allow_html=True)



# -- Render --


def render(services: dict) -> None:
    st.subheader("📊 Dashboard de Control y Diagnósticos")

    if st.button("🔄 Refrescar todos los datos desde SAP", type="primary"):
        st.session_state.pop("df_correctivas", None)
        st.session_state.pop("df_garantias", None)
        st.session_state.pop("df_pipeline_comercial", None)
        st.rerun()

    df_corr = _load_correctivas(services)
    df_gar = _load_garantias(services)
    df_com = _load_comercial(services)

    # ── Row 1: KPIs resumen ──
    st.divider()
    st.subheader("📈 KPIs en Tiempo Real")

    col_cantidad = _find_column(df_corr, ["cantidad", "llamadas", "correctivas"]) if df_corr is not None else None
    col_cliente_corr = _find_column(df_corr, ["cliente"]) if df_corr is not None else None
    col_equipo_corr = _find_column(df_corr, ["equipo"]) if df_corr is not None else None

    total_calls = 0
    equipos_afectados = 0
    clientes_afectados = 0
    if df_corr is not None and not df_corr.empty and col_cantidad:
        s = pd.to_numeric(df_corr[col_cantidad], errors="coerce")
        total_calls = int(s.sum())
        equipos_afectados = df_corr[col_equipo_corr].nunique() if col_equipo_corr else 0
        clientes_afectados = df_corr[col_cliente_corr].nunique() if col_cliente_corr else 0

    col_dias = _find_column(df_gar, ["días", "vencer", "dias"]) if df_gar is not None else None

    total_gar = 0
    avg_dias = 0.0
    criticas_count = 0
    if df_gar is not None and not df_gar.empty:
        total_gar = len(df_gar)
        if col_dias:
            s = pd.to_numeric(df_gar[col_dias], errors="coerce")
            avg_dias = s.mean()
            criticas_count = int((s <= 30).sum())

    r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns(6)
    _metric_card(r1c1, "🔧 Correctivas", total_calls,
                 severity=_severity(total_calls, warn=30, danger=60))
    _metric_card(r1c2, "🏥 Equipos", equipos_afectados)
    _metric_card(r1c3, "👥 Clientes", clientes_afectados)
    _metric_card(r1c4, "⏳ Garantías", total_gar)
    _metric_card(r1c5, "📅 Días Prom.", f"{avg_dias:.0f}")
    _metric_card(r1c6, "🚨 Críticas ≤30d", criticas_count,
                 severity=_severity(criticas_count, warn=5, danger=10),
                 delta="⚠️ requiere atención" if criticas_count >= 5 else "")

    # ── Row 2: Pipeline Comercial funnel ──
    st.divider()
    st.subheader("🎯 Pipeline Comercial")

    if df_com is not None and not df_com.empty:
        df_com = _derive_pipeline_stage(df_com)
        col_etapa = _find_column(df_com, ["etapa", "pipeline", "stage"])
        col_llamadas = _find_column(df_com, ["llamadas", "correctivas", "cantidad"])
        col_cliente_com = _find_column(df_com, ["cliente"])

        if col_etapa:
            stage_counts = df_com[col_etapa].value_counts()
            fun_cols = st.columns(len(PIPELINE_STAGES))
            for idx, stage in enumerate(PIPELINE_STAGES):
                cnt = stage_counts.get(stage, 0)
                sev = (
                    "danger" if stage == "Oportunidad Venta" and cnt > 20
                    else "warn" if stage == "Oportunidad Venta" and cnt > 10
                    else "ok"
                )
                _metric_card(fun_cols[idx], f"{STAGE_ICONS.get(stage, '⚪')} {stage}",
                           cnt, severity=sev)

            # Detail with stage filter
            st.divider()
            selected = st.selectbox("Filtrar por etapa", ["Todas"] + PIPELINE_STAGES)
            filtered = df_com if selected == "Todas" else df_com[df_com[col_etapa] == selected]

            if not filtered.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Equipos en etapa", len(filtered))
                if col_cliente_com:
                    c2.metric("Clientes", filtered[col_cliente_com].nunique())
                if col_llamadas:
                    s = pd.to_numeric(filtered[col_llamadas], errors="coerce")
                    c3.metric("Llamadas Correctivas", int(s.sum()) if s.notna().any() else 0)

            st.dataframe(filtered, use_container_width=True, height=300)

        # Top clients ranking
        if col_etapa and col_cliente_com and col_llamadas:
            st.divider()
            st.subheader("🏆 Top Clientes por Oportunidad")
            opp = df_com[df_com[col_etapa] == "Oportunidad Venta"]
            if not opp.empty:
                num = opp.copy()
                num[col_llamadas] = pd.to_numeric(num[col_llamadas], errors="coerce")
                top = (
                    num.groupby(col_cliente_com)[col_llamadas]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                st.bar_chart(top)
            else:
                st.success("Sin oportunidades de venta en este momento.")
    else:
        st.info("Cargando pipeline comercial... ejecutá el refresco si no aparece.")

    # ── Row 3: Detalle tablas (expandable) ──
    st.divider()

    tab1, tab2, tab3 = st.tabs(["📋 Correctivas", "📋 Garantías 90d", "📋 Pipeline Completo"])
    with tab1:
        if df_corr is not None and not df_corr.empty:
            st.dataframe(df_corr, use_container_width=True, height=350)
        else:
            st.info("Sin datos de correctivas.")
    with tab2:
        if df_gar is not None and not df_gar.empty:
            st.dataframe(df_gar, use_container_width=True, height=350)
        else:
            st.info("Sin datos de garantías.")
    with tab3:
        if df_com is not None and not df_com.empty:
            st.dataframe(df_com, use_container_width=True, height=350)
        else:
            st.info("Sin datos de pipeline comercial.")