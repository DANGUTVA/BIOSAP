"""KPI Dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find a column by partial match (case-insensitive)."""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def _load_dashboard_data(services: dict[str, object]) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Run live queries for correctivas and garantias if not already cached."""
    if "df_correctivas" not in st.session_state or "df_garantias" not in st.session_state:
        with st.spinner("Cargando datos de SAP..."):
            try:
                res_corr = services["pipeline"].execute(
                    query_id="llamadas_correctivas_division",
                    correlation_id="dashboard-correctivas",
                )
                st.session_state["df_correctivas"] = res_corr["data"]
            except Exception as exc:
                st.error(f"Error cargando correctivas: {exc}")
                st.session_state["df_correctivas"] = None

            try:
                res_gar = services["pipeline"].execute(
                    query_id="garantias_90_dias",
                    correlation_id="dashboard-garantias",
                )
                st.session_state["df_garantias"] = res_gar["data"]
            except Exception as exc:
                st.error(f"Error cargando garantías: {exc}")
                st.session_state["df_garantias"] = None

    return st.session_state.get("df_correctivas"), st.session_state.get("df_garantias")


def render(services: dict[str, object]) -> None:
    st.subheader("KPI Dashboard Biomédico")

    if st.button("Refrescar datos desde SAP", type="primary"):
        st.session_state.pop("df_correctivas", None)
        st.session_state.pop("df_garantias", None)
        st.rerun()

    df_corr, df_gar = _load_dashboard_data(services)

    if df_corr is None and df_gar is None:
        st.warning("No se pudieron cargar datos. Verifica la conexión SAP.")
        return

    st.divider()

    # --- Correctivas KPIs ---
    st.subheader("Llamadas Correctivas")
    if df_corr is not None and not df_corr.empty:
        col_correctivas = _find_column(df_corr, ["cantidad", "llamadas", "correctivas"])
        col_equipo = _find_column(df_corr, ["equipo"])
        col_cliente = _find_column(df_corr, ["cliente"])

        if col_correctivas:
            col_total = pd.to_numeric(df_corr[col_correctivas], errors="coerce").sum()
        else:
            st.warning("No se encontró columna de cantidad de correctivas.")
            col_total = 0

        unique_equipos = df_corr[col_equipo].nunique() if col_equipo else 0
        unique_clientes = df_corr[col_cliente].nunique() if col_cliente else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Correctivas", int(col_total))
        c2.metric("Equipos Afectados", unique_equipos)
        c3.metric("Clientes Afectados", unique_clientes)

        if col_correctivas and col_cliente:
            st.subheader("Top Clientes por Correctivas")
            df_corr[col_correctivas] = pd.to_numeric(df_corr[col_correctivas], errors="coerce")
            top_clientes = (
                df_corr.groupby(col_cliente)[col_correctivas]
                .sum()
                .sort_values(ascending=False)
                .head(5)
            )
            st.bar_chart(top_clientes)

        st.subheader("Detalle Correctivas")
        st.dataframe(df_corr, use_container_width=True)

    else:
        st.info("Sin datos de correctivas.")

    st.divider()

    # --- Garantías KPIs ---
    st.subheader("Garantías Próximas a Vencer (90 días)")
    if df_gar is not None and not df_gar.empty:
        col_dias = _find_column(df_gar, ["días", "vencer", "dias"])
        
        total_garantias = len(df_gar)
        avg_dias = 0
        criticas = pd.DataFrame()
        
        if col_dias:
            df_gar[col_dias] = pd.to_numeric(df_gar[col_dias], errors="coerce")
            avg_dias = df_gar[col_dias].mean()
            criticas = df_gar[df_gar[col_dias] <= 30]

        c1, c2, c3 = st.columns(3)
        c1.metric("Garantías por Vencer", total_garantias)
        c2.metric("Promedio Días Restantes", f"{avg_dias:.0f} días")
        c3.metric("Críticas (<= 30 días)", len(criticas))

        st.subheader("Equipos con Garantía Crítica")
        if not criticas.empty:
            st.dataframe(criticas, use_container_width=True)
        else:
            st.success("No hay garantías críticas en los próximos 30 días.")

        st.subheader("Detalle Garantías")
        st.dataframe(df_gar, use_container_width=True)

    else:
        st.info("Sin datos de garantías.")
