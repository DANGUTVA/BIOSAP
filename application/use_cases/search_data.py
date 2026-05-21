"""Use case: search and filter dataframe rows."""

from __future__ import annotations

import pandas as pd


class SearchDataUseCase:
    """Performs case-insensitive global text filtering."""

    def execute(
        self,
        df: pd.DataFrame,
        text: str,
        selected_columns: list[str] | None = None,
        column_terms: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        filtered_df = df

        if text.strip():
            global_mask = filtered_df.astype(str).apply(
                lambda col: col.str.contains(text, case=False, na=False, regex=False)
            ).any(axis=1)
            filtered_df = filtered_df[global_mask]

        active_columns = [col for col in (selected_columns or []) if col in filtered_df.columns]
        active_terms = column_terms or {}

        for column in active_columns:
            term = active_terms.get(column, "")
            if term.strip():
                column_mask = filtered_df[column].astype(str).str.contains(
                    term,
                    case=False,
                    na=False,
                    regex=False,
                )
                filtered_df = filtered_df[column_mask]

        return filtered_df
