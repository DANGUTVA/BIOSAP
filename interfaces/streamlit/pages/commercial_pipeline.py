"""Commercial Pipeline page — opportunities by stage."""

from __future__ import annotations

import pandas as pd
import streamlit as st


PIPELINE_STAGES = [
    "Oportunidad Venta",
    "En Garantía",
    "Otro",
]


STAGE_COLORS = {
    "Oportunidad Venta": "🔴",
    "En Garantía": "🟢",
    "Otro": "⚪",
}


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find a column by partial match (case-insensitive)."""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def _derive_pipeline_stage(df: pd.DataFrame) -> pd.DataFrame:
    """Classify each row into a commercial pipeline stage.

    The classification is derived from WarrantyStatus (Estado Contrato):
    - 'Sin_Contrato' → opportunity for sale of a new contract
    - containing 'Garantía' → equipment under warranty (potential renewal)
    - everything else → 'Otro'
    """
    col_estado = _find_column(df, ["estado", "contrato", "warranty"])
    if col_estado is None:
        return df

    df = df.copy()
    df["Etapa Pipeline"] = "Otro"
    df.loc[df[col_estado] == "Sin_Contrato", "Etapa Pipeline"] = "Oportunidad Venta"
    mask_garantia = df[col_estado].astype(str).str.contains("Garant", case=False, na=False)
    df.loc[mask_garantia, "Etapa Pipeline"] = "En Garantía"
    return df


def _load_pipeline(services: dict[str, object]) -> pd.DataFrame | None:
    """Load commercial pipeline data from SAP."""
    cache_key = "df_pipeline_comercial"
    if cache_key not in st.session_state:
        with st.spinner("Cargando pipeline comercial desde SAP..."):
            try:
                res = services["pipeline"].execute(
                    query_id="pipeline_comercial",
                    correlation_id="commercial-pipeline",
                )
                st.session_state[cache_key] = res["data"]
            except Exception as exc:
                st.error(f"Error cargando pipeline comercial: {exc}")
                return None
    return st.session_state.get(cache_key)


def render(services: dict[str, object]) -> None:
    st.subheader("Pipeline Comercial — Imágenes Médicas")

    if st.button("Refrescar datos", type="primary"):
        st.session_state.pop("df_pipeline_comercial", None)
        st.rerun()

    df = _load_pipeline(services)
    if df is None or df.empty:
        st.info("No hay datos disponibles para el pipeline comercial.")
        return

    # Derive pipeline stages in Python (safer than SQL CASE WHEN)
    df = _derive_pipeline_stage(df)

    # --- Column detection ---
    col_etapa = _find_column(df, ["etapa", "pipeline", "stage"])
    col_cliente = _find_column(df, ["cliente"])
    col_equipo = _find_column(df, ["equipo"])
    col_llamadas = _find_column(df, ["llamadas", "correctivas", "cantidad"])
    col_estado = _find_column(df, ["estado", "contrato"])
    col_dias = _find_column(df, ["días", "vencer", "dias"])

    # --- Funnel metrics ---
    st.subheader("Embudo de Oportunidades")

    if col_etapa:
        stage_counts = df[col_etapa].value_counts()

        cols = st.columns(len(PIPELINE_STAGES))
        for idx, stage in enumerate(PIPELINE_STAGES):
            count = stage_counts.get(stage, 0)
            icon = STAGE_COLORS.get(stage, "⚪")
            with cols[idx]:
                st.metric(label=f"{icon} {stage}", value=count)

    # --- Detail table by stage ---
    st.divider()

    if col_etapa:
        selected_stage = st.selectbox(
            "Filtrar por etapa",
            options=["Todas"] + PIPELINE_STAGES,
        )

        if selected_stage == "Todas":
            filtered = df
        else:
            filtered = df[df[col_etapa] == selected_stage]

        # Summary metrics for filtered view
        if not filtered.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Equipos", len(filtered))
            if col_cliente:
                c2.metric("Clientes", filtered[col_cliente].nunique())
            if col_llamadas:
                total_calls = pd.to_numeric(filtered[col_llamadas], errors="coerce").sum()
                c3.metric("Llamadas Correctivas", int(total_calls) if pd.notna(total_calls) else 0)

        st.dataframe(filtered, use_container_width=True)

    else:
        # Fallback: show raw data without stage grouping
        st.warning("No se encontró columna 'Etapa Pipeline'. Mostrando datos sin clasificar.")
        st.dataframe(df, use_container_width=True)

    # --- Top clients by corrective calls (opportunity ranking) ---
    if col_etapa and col_cliente and col_llamadas:
        st.divider()
        st.subheader("Top Clientes por Oportunidad")

        # Show clients ranked by corrective calls in non-guarantee stages
        opportunity_stages = ["Oportunidad Venta"]
        opp_df = df[df[col_etapa].isin(opportunity_stages)]

        if not opp_df.empty:
            opp_df_numeric = opp_df.copy()
            opp_df_numeric[col_llamadas] = pd.to_numeric(
                opp_df_numeric[col_llamadas], errors="coerce"
            )
            top_clients = (
                opp_df_numeric.groupby(col_cliente)[col_llamadas]
                .sum()
                .sort_values(ascending=False)
                .head(10)
            )
            st.bar_chart(top_clients)
        else:
            st.success("No hay oportunidades urgentes en este momento.")