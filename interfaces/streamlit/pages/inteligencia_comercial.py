"""Inteligencia Comercial — filtros dinámicos, KPIs automáticos, estadísticas y recomendaciones."""

from __future__ import annotations

import pathlib
from datetime import date

import pandas as pd
import streamlit as st

from domain.models.commercial import CommercialFilter


# ── Helpers ──────────────────────────────────────────────────────────────


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find column by keywords, preferring exact name match then longest substring match."""
    keywords_lower = [kw.lower() for kw in keywords]
    # First pass: exact column name match (case-insensitive)
    for col in df.columns:
        if str(col).strip().lower() in keywords_lower:
            return col
    # Second pass: substring match, preferring longest keyword match
    best = None
    best_len = 0
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords_lower:
            if kw in col_lower and len(kw) > best_len:
                best = col
                best_len = len(kw)
    return best


def _unique_values(df: pd.DataFrame, col: str | None) -> list[str]:
    if col is None or col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).unique().tolist())


def _format_currency(value: float) -> str:
    if value == 0:
        return "₡0"
    if value >= 1_000_000:
        return f"₡{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"₡{value/1_000:.0f}K"
    return f"₡{value:.0f}"


def _format_number(value: float, decimals: int = 1) -> str:
    if value == float("inf"):
        return "∞"
    if value == 0:
        return "0"
    return f"{value:.{decimals}f}"


def _metric_card(col, label: str, value, *, severity: str = "ok", delta: str = "") -> None:
    severity_class = f"metric-{severity}"
    delta_html = f'<div class="metric-card-delta">{delta}</div>' if delta else ""
    card_html = f"""
    <div class="metric-card {severity_class}">
        <div class="metric-card-title">{label}</div>
        <div class="metric-card-value">{value}</div>
        {delta_html}
    </div>
    """
    with col:
        st.markdown(card_html, unsafe_allow_html=True)


def _apply_client_side_filter(df: pd.DataFrame, filtros: CommercialFilter) -> pd.DataFrame:
    """Apply filters client-side without re-executing the SAP query."""
    if filtros is None:
        return df
    result = df.copy()

    if filtros.marca:
        col = _find_column(result, ["marca", "brand"])
        if col:
            result = result[result[col].astype(str).str.contains(filtros.marca, case=False, na=False, regex=False)]

    if filtros.modelo:
        col = _find_column(result, ["modelo", "model"])
        if col:
            result = result[result[col].astype(str).str.contains(filtros.modelo, case=False, na=False, regex=False)]

    if filtros.cliente:
        col = _find_column(result, ["cliente", "cardname", "customer"])
        if col:
            result = result[result[col].astype(str).str.contains(filtros.cliente, case=False, na=False, regex=False)]

    if filtros.fecha_desde:
        col = _find_column(result, ["fecha llamada", "fecha", "call date"])
        if col:
            fechas = pd.to_datetime(result[col], errors="coerce")
            desde = pd.Timestamp(filtros.fecha_desde)
            result = result[fechas >= desde]

    if filtros.fecha_hasta:
        col = _find_column(result, ["fecha llamada", "fecha", "call date"])
        if col:
            fechas = pd.to_datetime(result[col], errors="coerce")
            hasta = pd.Timestamp(filtros.fecha_hasta)
            result = result[fechas <= hasta]

    return result


# ── Render ────────────────────────────────────────────────────────────────


def render(services: dict) -> None:
    st.subheader("📈 Inteligencia Comercial")

    # ── Division selector ──────────────────────────────────────────
    division_options = ["Imágenes Médicas"]

    st.markdown("##### 🔎 Filtros de Búsqueda")
    st.caption("Completá los filtros y presioná **Buscar Datos** para consultar SAP.")

    c_div, c_refresh = st.columns([3, 1])
    with c_div:
        selected_division = st.selectbox(
            "División",
            options=division_options,
            index=0,
            key="intel_division",
            help="Seleccioná la división. Se envía como parámetro al query SAP.",
        )
    with c_refresh:
        st.write("")
        st.write("")
        if st.button("🗑️ Limpiar", help="Borra los datos cargados y los filtros"):
            # Clear cached data
            keys_to_clear = [k for k in st.session_state if k.startswith("df_intel_comercial")]
            for k in keys_to_clear:
                del st.session_state[k]
            # Reset filter inputs
            st.session_state["intel_marca"] = ""
            st.session_state["intel_modelo"] = ""
            st.session_state["intel_cliente"] = ""
            st.session_state["intel_fecha_desde"] = None
            st.session_state["intel_fecha_hasta"] = None
            st.rerun()

    # ── Filter inputs (always visible, no data dependency) ──────────
    f1, f2 = st.columns(2)
    with f1:
        marca_input = st.text_input(
            "Marca", value="", placeholder="Todas", key="intel_marca",
            help="Escribí parte del nombre o dejá vacío para todas.",
        )
    with f2:
        modelo_input = st.text_input(
            "Modelo", value="", placeholder="Todos", key="intel_modelo",
            help="Escribí parte del nombre o dejá vacío para todos.",
        )

    f3, f4, f5 = st.columns(3)
    with f3:
        cliente_input = st.text_input(
            "Cliente", value="", placeholder="Todos", key="intel_cliente",
            help="Escribí parte del nombre o dejá vacío para todos.",
        )
    with f4:
        fecha_desde = st.date_input("Desde", value=None, key="intel_fecha_desde", help="Fecha de llamada desde.")
    with f5:
        fecha_hasta = st.date_input("Hasta", value=None, key="intel_fecha_hasta", help="Fecha de llamada hasta.")

    # ── Search button ──────────────────────────────────────────────
    buscar = st.button("🔍 Buscar Datos", type="primary", use_container_width=True)

    # ── Load data when button is clicked (always fresh, no stale cache) ──
    cache_key = f"df_intel_comercial_{selected_division}"

    if buscar:
        # Always clear previous cache so we get fresh data
        st.session_state.pop(cache_key, None)
        with st.spinner(f"Consultando SAP para {selected_division}..."):
            try:
                result = services["commercial_intelligence"].execute(division=selected_division)
                st.session_state[cache_key] = result
            except Exception as exc:
                st.error(f"Error cargando datos: {exc}")
                st.session_state[cache_key] = None

    # ── Check if we have data to show ───────────────────────────────
    if cache_key not in st.session_state:
        st.info("Seleccioná los filtros y presioná **🔍 Buscar Datos** para consultar.")
        return

    result = st.session_state.get(cache_key)
    if result is None:
        st.warning("No se pudieron cargar los datos. Intentá de nuevo.")
        return

    df_raw = result.get("data")
    if df_raw is None or (isinstance(df_raw, pd.DataFrame) and df_raw.empty):
        st.warning(f"El query SAP no devolvió datos para **{selected_division}**. Verificá que la división exista y que haya datos en OCTR/FA_OSCL.")
        return

    # ── Apply client-side filters to the loaded data ────────────────
    filtros = CommercialFilter(
        division=selected_division,
        marca=marca_input.strip() if marca_input.strip() else None,
        modelo=modelo_input.strip() if modelo_input.strip() else None,
        cliente=cliente_input.strip() if cliente_input.strip() else None,
        fecha_desde=fecha_desde if fecha_desde else None,
        fecha_hasta=fecha_hasta if fecha_hasta else None,
    )

    df = _apply_client_side_filter(df_raw, filtros)

    # Recompute KPIs/stats on filtered data
    compute_kpis = services["compute_commercial_kpis"]
    compute_recs = services["compute_recommendations"]
    filtered_stats = compute_kpis.compute_stats(df)
    filtered_kpis = compute_kpis.compute_kpis(df)
    filtered_by_equipment = compute_kpis.compute_kpis_by_equipment(df)
    merged = services["commercial_intelligence"]._merge_original_columns(df, filtered_by_equipment)
    filtered_recommendations = compute_recs.execute(merged, filtered_kpis)

    if df.empty:
        st.warning(f"Hice el query y obtuve {len(df_raw)} registros, pero **{len(df)} coinciden** con los filtros. Probá con filtros más amplios.")
        if filtros.marca:
            st.caption(f"💡 Sugerencia: la marca **{filtros.marca}** no está en los datos. Marcas disponibles: {', '.join(df_raw['Marca'].dropna().unique().astype(str).tolist())}")
        return

    # ── Show filter summary ────────────────────────────────────────
    active_filters = []
    if filtros.marca:
        active_filters.append(f"Marca: **{filtros.marca}**")
    if filtros.modelo:
        active_filters.append(f"Modelo: **{filtros.modelo}**")
    if filtros.cliente:
        active_filters.append(f"Cliente: **{filtros.cliente}**")
    if filtros.fecha_desde:
        active_filters.append(f"Desde: **{filtros.fecha_desde}**")
    if filtros.fecha_hasta:
        active_filters.append(f"Hasta: **{filtros.fecha_hasta}**")

    filter_summary = f"División: **{selected_division}**"
    if active_filters:
        filter_summary += " | " + " | ".join(active_filters)
    st.caption(f"Mostrando {len(df)} registros de {len(df_raw)} totales. {filter_summary}")

    # ── Row 1: KPI cards ────────────────────────────────────────────
    st.divider()
    st.subheader("📊 KPIs Automáticos")

    k = filtered_kpis

    # Severity for MTBF: low = good, high = bad
    mtbf_sev = "ok" if k.mtbf_dias >= 120 else ("warn" if k.mtbf_dias >= 60 else "danger")

    # Severity for riesgo
    riesgo_val = k.riesgo
    if riesgo_val == float("inf"):
        riesgo_sev = "danger"
        riesgo_display = "∞"
    elif riesgo_val > 3.0:
        riesgo_sev = "danger"
        riesgo_display = f"{riesgo_val:.1f}"
    elif riesgo_val > 1.5:
        riesgo_sev = "warn"
        riesgo_display = f"{riesgo_val:.1f}"
    else:
        riesgo_sev = "ok"
        riesgo_display = f"{riesgo_val:.1f}"

    # Severity for cumplimiento PM: >=1 = ok, <0.5 = danger
    cumpl_val = k.cumplimiento_pm
    if cumpl_val == float("inf"):
        cumpl_sev = "warn"
        cumpl_display = "∞"
    elif cumpl_val >= 1.0:
        cumpl_sev = "ok"
        cumpl_display = f"{cumpl_val:.0%}"
    elif cumpl_val >= 0.5:
        cumpl_sev = "warn"
        cumpl_display = f"{cumpl_val:.0%}"
    else:
        cumpl_sev = "danger"
        cumpl_display = f"{cumpl_val:.0%}"

    k1, k2, k3 = st.columns(3)
    _metric_card(k1, "🔧 MTBF", f"{_format_number(k.mtbf_dias, 0)} días", severity=mtbf_sev)
    _metric_card(k2, "📅 PM Anual", _format_number(k.pm_anual), severity="ok" if k.pm_anual > 0 else "warn")
    _metric_card(k3, "📆 PM Esperados", _format_number(k.pm_esperados), severity="ok" if k.pm_esperados > 0 else "warn")

    k4, k5, k6 = st.columns(3)
    _metric_card(k4, "⚠️ Riesgo", riesgo_display, severity=riesgo_sev)
    _metric_card(k5, "✅ Cumplimiento PM", cumpl_display, severity=cumpl_sev)
    _metric_card(k6, "💰 Precio Sugerido", _format_currency(k.precio_sugerido))

    # ── Row 2: Estadísticas ─────────────────────────────────────────
    st.divider()
    st.subheader("📋 Estadísticas")

    s = filtered_stats
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Precio Prom.", _format_currency(s.precio_promedio))
    s2.metric("Precio Mín.", _format_currency(s.precio_min))
    s3.metric("Precio Máx.", _format_currency(s.precio_max))
    s4.metric("Correctivos Prom.", _format_number(s.correctivos_promedio))
    s5.metric("PM Prom.", _format_number(s.pm_promedio))

    # ── Row 3: Recomendaciones ───────────────────────────────────────
    if filtered_recommendations:
        st.divider()
        st.subheader("🔄 Recomendaciones")

        for rec in filtered_recommendations:
            icon = {"urgente": "🔴", "advertencia": "🟡", "oportunidad": "🟢"}.get(rec.tipo, "⚪")
            st.markdown(f"{icon} **{rec.equipo}** (SN: {rec.serial}) — {rec.cliente}: {rec.mensaje}")

    # ── Row 4: Detail tables ────────────────────────────────────────
    st.divider()

    tab_detail, tab_equip, tab_contracts = st.tabs([
        "📋 Detalle Llamadas",
        "🔢 Por Equipo",
        "📄 Contratos",
    ])

    with tab_detail:
        col_tipo = _find_column(df, ["tipo llamada", "call type", "tipo_llamada"])
        if col_tipo and col_tipo in df.columns:
            display_df = df.copy()
            display_df["Tipo"] = display_df[col_tipo].astype(str).map(
                {"1": "Preventivo", "2": "Correctivo"}
            ).fillna(display_df[col_tipo].astype(str))
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.dataframe(df, use_container_width=True, height=400)

    with tab_equip:
        if filtered_by_equipment is not None and not filtered_by_equipment.empty:
            display_eq = filtered_by_equipment.copy()
            riesgo_col = "Riesgo"
            if riesgo_col in display_eq.columns:
                display_eq[riesgo_col] = display_eq[riesgo_col].apply(
                    lambda x: "∞" if x == float("inf") else f"{x:.1f}"
                )
            st.dataframe(display_eq, use_container_width=True, height=400)
        else:
            st.info("Sin datos por equipo.")

    with tab_contracts:
        contract_keywords = [
            "cliente", "equipo", "modelo", "serie", "contrato", "monto",
            "inicio", "fin", "estado", "garantía", "ubicación", "periodicidad",
            "moneda", "renovación",
        ]
        contract_cols = []
        for c in df.columns:
            c_lower = str(c).lower()
            if any(kw in c_lower for kw in contract_keywords):
                contract_cols.append(c)

        # Exclude call-type columns from contract view
        col_tipo_llamada = _find_column(df, ["tipo llamada", "call type", "tipo_llamada", "fecha llamada"])
        exclude_cols = {col_tipo_llamada} if col_tipo_llamada else set()
        display_contract_cols = [c for c in contract_cols if c not in exclude_cols and c in df.columns]

        if display_contract_cols:
            contract_df = df[display_contract_cols].drop_duplicates()
            st.dataframe(contract_df, use_container_width=True, height=400)
        else:
            st.dataframe(df, use_container_width=True, height=400)

    # ── Export ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Exportar Datos")

    export_df = filtered_by_equipment if filtered_by_equipment is not None and not filtered_by_equipment.empty else df
    st.caption(f"Total: **{len(export_df)}** filas × **{len(export_df.columns)}** columnas")

    default_name = f"inteligencia_comercial_{selected_division.lower().replace(' ', '_')}"
    filename = st.text_input("Nombre base", value=default_name)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("📄 Exportar CSV", use_container_width=True, key="export_intel_csv"):
            path = services["export"].to_csv(export_df, pathlib.Path("outputs") / f"{filename}.csv")
            st.success(f"✅ CSV: {path}")
    with col_exp2:
        if st.button("📊 Exportar XLSX", use_container_width=True, key="export_intel_xlsx"):
            path = services["export"].to_xlsx(export_df, pathlib.Path("outputs") / f"{filename}.xlsx")
            st.success(f"✅ XLSX: {path}")