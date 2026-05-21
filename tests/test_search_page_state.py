from interfaces.streamlit.pages.search import _clear_search_filters


def test_clear_search_filters_resets_widget_state() -> None:
    session_state = {
        "search_text": "acme",
        "search_selected_columns": ["Division"],
        "search_column_terms": {"Division": "ret"},
        "search_term_Division": "ret",
        "unrelated": "keep",
    }

    _clear_search_filters(
        session_state,
        search_key="search_text",
        selected_cols_key="search_selected_columns",
        terms_key="search_column_terms",
    )

    assert session_state["search_text"] == ""
    assert session_state["search_selected_columns"] == []
    assert session_state["search_column_terms"] == {}
    assert "search_term_Division" not in session_state
    assert session_state["unrelated"] == "keep"


def test_clear_search_filters_removes_all_stale_dynamic_keys() -> None:
    session_state = {
        "search_text": "glob",
        "search_selected_columns": ["CardName", "Division"],
        "search_column_terms": {"CardName": "glob", "Division": "ind"},
        "search_term_CardName": "glob",
        "search_term_Division": "ind",
    }

    _clear_search_filters(
        session_state,
        search_key="search_text",
        selected_cols_key="search_selected_columns",
        terms_key="search_column_terms",
    )

    assert "search_term_CardName" not in session_state
    assert "search_term_Division" not in session_state
