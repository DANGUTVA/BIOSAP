"""Pipeline page."""

import traceback
import streamlit as st


def render(services: dict[str, object]) -> None:
    st.subheader("Pipeline")
    catalog = services["catalog"]
    queries = catalog.list_queries()
    query_ids = [q["id"] for q in queries]
    query_id = st.selectbox("Query", query_ids)
    if st.button("Run pipeline", type="primary"):
        try:
            result = services["pipeline"].execute(query_id=query_id, correlation_id="streamlit")
            st.session_state["current_df"] = result["data"]
            st.success(f"Loaded {len(result['data'])} rows from {query_id}")
            st.json(result["meta"])
        except Exception as exc:  # pragma: no cover - runtime UX path
            message = str(exc)
            likely_cause = "Likely cause: SAP login selector changed or SAP page loaded too slowly."
            st.error(f"Pipeline failed for '{query_id}'. {likely_cause}")
            with st.expander("Technical details"):
                st.text(message)
                st.text(traceback.format_exc())
