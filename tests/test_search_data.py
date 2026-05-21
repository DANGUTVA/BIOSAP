import pandas as pd

from application.use_cases.search_data import SearchDataUseCase


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CardCode": ["C0001", "C0002", "C0003"],
            "CardName": ["Acme Corp", "Globex", "Initech"],
            "Division": ["Retail", "Industrial", "Retail"],
        }
    )


def test_global_search_works() -> None:
    df = _sample_df()
    result = SearchDataUseCase().execute(df, "acme")
    assert len(result) == 1
    assert result.iloc[0]["CardCode"] == "C0001"


def test_column_specific_filter_works() -> None:
    df = _sample_df()
    result = SearchDataUseCase().execute(
        df,
        "",
        selected_columns=["Division"],
        column_terms={"Division": "ret"},
    )
    assert len(result) == 2
    assert set(result["CardCode"].tolist()) == {"C0001", "C0003"}


def test_empty_criteria_returns_original_dataframe() -> None:
    df = _sample_df()
    result = SearchDataUseCase().execute(df, "")
    pd.testing.assert_frame_equal(result, df)
