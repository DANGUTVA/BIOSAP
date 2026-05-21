"""Search page with LIVE data support."""

from __future__ import annotations

import streamlit as st
import pandas as pd
from collections.abc import MutableMapping
from typing import Any


def _example_values(df: pd.DataFrame, max_columns: int = 3, max_values: int = 3) -> str:
    examples: list[str] = []
    for column in df.columns[:max_columns]:
        values = [str(v) for v in df[column].dropna().astype(str).unique()[:max_values]]
        if values:
            examples.append(f"{column}: {', '.join(values)}")
    return " | ".join(examples)


def _clear_search_filters(
    session_state: MutableMapping[str, Any],
    *,
    search_key: str,
    selected_cols_key: str,
    terms_key: str,
    dynamic_term_prefix: str = "search_term_",
) -> None:
    session_state[search_key] = ""
    session_state[selected_cols_key] = []
    session_state[terms_key] = {}

    stale_dynamic_keys = [
        key for key in list(session_state.keys()) if key.startswith(dynamic_term_prefix)
    ]
    for key in stale_dynamic_keys:
        del session_state[key]


def _load_search_dataset(
    services: dict[str, object],
    query_id: str,
    *,
    param_overrides: dict[int, str] | None = None,
) -> pd.DataFrame | None:
    """Load a dataset from SAP or session cache."""
    # Different serial numbers → different cache keys
    suffix = ""
    if param_overrides:
        suffix = "_" + "_".join(str(v) for v in param_overrides.values())
    cache_key = f"search_df_{query_id}{suffix}"
    if cache_key not in st.session_state:
        with st.spinner(f"Cargando {query_id} desde SAP..."):
            try:
                res = services["pipeline"].execute(
                    query_id=query_id,
                    correlation_id=f"search-{query_id}",
                    param_overrides=param_overrides,
                )
                st.session_state[cache_key] = res["data"]
            except Exception as exc:
                st.error(f"Error cargando {query_id}: {exc}")
                return None
    return st.session_state.get(cache_key)


def render(services: dict[str, object]) -> None:
    st.subheader("Buscador de Equipos y Clientes")

    # Dataset selector
    dataset_options = {
        "Llamadas Correctivas por Division": "llamadas_correctivas_division",
        "Garantia a Vencer en 90 Dias": "garantias_90_dias",
        "Llamadas Correctivas por Numero de Serie": "llamadas_correctivas_serial",
    }
    
    selected_label = st.selectbox(
        "Dataset a buscar",
        options=list(dataset_options.keys()),
    )
    query_id = dataset_options[selected_label]

    # Serial input — appears only when the serial query is selected
    serial: str = ""
    if query_id == "llamadas_correctivas_serial":
        serial = st.text_input(
            "Número de Serie",
            value="",
            placeholder="Ej: 650017",
            help="Ingresá el número de serie del equipo a buscar.",
        )

    if st.button("Cargar / Refrescar datos"):
        st.session_state.pop(f"search_df_{query_id}", None)
        if serial:
            st.session_state.pop(f"search_df_{query_id}_{serial}", None)
        st.rerun()

    param_overrides: dict[int, str] | None = None
    if serial.strip():
        param_overrides = {0: serial.strip()}

    df = _load_search_dataset(services, query_id, param_overrides=param_overrides)

    if df is None or df.empty:
        st.info("No hay datos disponibles para este dataset.")
        return

    search_key = "search_text"
    selected_cols_key = "search_selected_columns"
    terms_key = "search_column_terms"

    if terms_key not in st.session_state:
        st.session_state[terms_key] = {}

    query = st.text_input("Buscar texto", key=search_key)
    st.caption(
        "Tip: busca por valores reales. "
        f"Ejemplos → {_example_values(df)}"
    )

    selected_columns = st.multiselect(
        "Filtrar por columnas (opcional)",
        options=list(df.columns),
        key=selected_cols_key,
    )

    st.button(
        "Limpiar filtros",
        on_click=_clear_search_filters,
        kwargs={
            "session_state": st.session_state,
            "search_key": search_key,
            "selected_cols_key": selected_cols_key,
            "terms_key": terms_key,
        },
    )

    column_terms: dict[str, str] = {}
    for column in selected_columns:
        value = st.text_input(
            f"Filtro '{column}' contiene",
            key=f"search_term_{column}",
        )
        column_terms[column] = value

    result = services["search"].execute(
        df,
        query,
        selected_columns=selected_columns,
        column_terms=column_terms,
    )
    st.write(f"Filas: {len(df)} → {len(result)} tras filtros")
    st.dataframe(result, use_container_width=True)
