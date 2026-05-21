"""Tests for Bs4HtmlTableParser — priority table selection and data extraction."""

import pandas as pd
import pytest

from infrastructure.html_parsers.bs4_parser import Bs4HtmlTableParser
from domain.errors import ParserError


@pytest.fixture
def parser() -> Bs4HtmlTableParser:
    return Bs4HtmlTableParser()


# -- Helper: minimal SAP-like page with the key structural elements ----------

def _sap_page(result_table_html: str) -> str:
    """Build a minimal SAP Query Manager page with a custom #result inner HTML."""
    return f"""<!DOCTYPE html>
<html><head><title>Query Manager</title></head><body>
<form id="form1">
<table id="queryContainer"><tr><td>
<textarea id="query">SELECT * FROM FA_OSCL</textarea>
</td></tr></table>
<div id="result">{result_table_html}</div>
</form>
</body></html>"""


def _result_table(headers: list[str], rows: list[list[str]], table_id: str = "Table1") -> str:
    """Build an SAP-style SearchResults table."""
    th_html = "".join(f"<th>{h}</th>" for h in headers)
    trs_html = ""
    for row in rows:
        tds_html = "".join(f"<td>{c}</td>" for c in row)
        trs_html += f"<tr>{tds_html}</tr>"
    return (
        f'<table id="{table_id}" class="SearchResults NoUnderline2">'
        f"<thead><tr>{th_html}</tr></thead>"
        f"<tbody>{trs_html}</tbody></table>"
    )


class TestFindResultTable:
    """Verify the parser picks the correct table (not queryContainer)."""

    def test_prefers_table_inside_result_div(self, parser: Bs4HtmlTableParser) -> None:
        """The parser must find the data table inside #result, not queryContainer."""
        result_html = _result_table(
            headers=["#", "Name", "Count"],
            rows=[["1", "Alpha", "10"], ["2", "Beta", "20"]],
        )
        page = _sap_page(result_html)
        df = parser.parse(page)

        assert len(df) == 2
        assert list(df.columns) == ["#", "Name", "Count"]
        assert df.iloc[0]["Name"] == "Alpha"

    def test_prefers_searchresults_class(self, parser: Bs4HtmlTableParser) -> None:
        """When no #result div exists, fall back to class=SearchResults."""
        table = _result_table(
            headers=["Col"],
            rows=[["val"]],
        )
        html = f"<html><body>{table}</body></html>"
        df = parser.parse(html)
        assert len(df) == 1
        assert df.iloc[0]["Col"] == "val"

    def test_prefers_table_with_th(self, parser: Bs4HtmlTableParser) -> None:
        """When no #result or SearchResults, pick the first table that has <th>."""
        html = """<html><body>
        <table id="layout"><tr><td>sidebar</td></tr></table>
        <table id="data"><tr><th>X</th></tr><tr><td>1</td></tr></table>
        </body></html>"""
        df = parser.parse(html)
        assert list(df.columns) == ["X"]
        assert len(df) == 1

    def test_fallback_first_table_uses_first_row_as_header(self, parser: Bs4HtmlTableParser) -> None:
        """Last resort: use the first table, and first data row becomes the header."""
        html = """<html><body>
        <table><tr><td>Name</td><td>Count</td></tr><tr><td>A</td><td>1</td></tr></table>
        </body></html>"""
        df = parser.parse(html)
        assert list(df.columns) == ["Name", "Count"]
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "A"

    def test_no_table_raises_parser_error(self, parser: Bs4HtmlTableParser) -> None:
        """When there is no table at all, raise ParserError."""
        with pytest.raises(ParserError, match="No data table found"):
            parser.parse("<html><body><p>No tables here</p></body></html>")

    def test_empty_result_table_returns_empty_df(self, parser: Bs4HtmlTableParser) -> None:
        """Table inside #result with headers but zero data rows → empty DataFrame."""
        result_html = _result_table(
            headers=["A", "B"],
            rows=[],
        )
        page = _sap_page(result_html)
        df = parser.parse(page)
        assert df.empty


class TestRealSapStructure:
    """Parse using an HTML structure matching the actual SAP Query Manager capture."""

    def test_sap_capture_structure_picks_data_table(self, parser: Bs4HtmlTableParser) -> None:
        """Reproduce the bug: queryContainer was picked instead of Table1."""
        # This mimics the real SAP page: a layout table (queryContainer) before
        # the #result div that contains the data table.
        result_html = _result_table(
            headers=["#", "División", "Cantidad"],
            rows=[
                ["1", "Imágenes Médicas", "16"],
                ["2", "Imágenes Médicas", "14"],
            ],
        )
        page = _sap_page(result_html)
        df = parser.parse(page)

        assert len(df) == 2
        assert "División" in df.columns
        assert df.iloc[0]["División"] == "Imágenes Médicas"
        # The queryContainer table has no <th> — parser must skip it.
        # The data must come from the SearchResults table inside #result.