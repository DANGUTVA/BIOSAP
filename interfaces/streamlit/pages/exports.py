"""Export page — CSV and XLSX from cached datasets."""

from pathlib import Path
import streamlit as st


DATASET_KEYS = {
    "Llamadas Correctivas por División": "df_correctivas",
    "Garantías 90 Días": "df_garantias",
    "Pipeline Comercial": "df_pipeline_comercial",
}


def render(services: dict[str, object]) -> None:
    st.subheader("Exportar Datos")

    available = [
        label for label, key in DATASET_KEYS.items()
        if key in st.session_state and st.session_state[key] is not None
    ]

    if not available:
        st.info("Primero cargá datos desde el Dashboard.")
        return

    selected_label = st.selectbox("Dataset a exportar", available)
    cache_key = DATASET_KEYS[selected_label]
    df = st.session_state[cache_key]

    st.caption(f"Total: **{len(df)}** filas × **{len(df.columns)}** columnas")

    # Preview
    st.subheader("🔍 Vista previa (primeras 10 filas)")
    st.dataframe(df.head(10), use_container_width=True, height=250)

    st.divider()
    filename = st.text_input("Nombre base", value=selected_label.lower().replace(" ", "_"))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Exportar CSV", use_container_width=True):
            path = services["export"].to_csv(df, Path("outputs") / f"{filename}.csv")
            st.success(f"✅ CSV: {path}")
    with col2:
        if st.button("📊 Exportar XLSX", use_container_width=True):
            path = services["export"].to_xlsx(df, Path("outputs") / f"{filename}.xlsx")
            st.success(f"✅ XLSX: {path}")