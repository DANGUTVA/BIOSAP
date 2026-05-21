"""BeautifulSoup parser for SAP HTML tables.

SAP Query Manager pages contain multiple tables (layout containers, the
query textarea table, and the actual results table). This parser uses a
priority strategy to find the right table:

1. Table inside ``div#result`` (SAP query results container)
2. Table with class ``SearchResults`` (SAP result table marker)
3. First table containing ``<th>`` elements (likely a data table)
4. Last resort: first table on the page
"""

import pandas as pd
from bs4 import BeautifulSoup
from domain.errors import ParserError
from infrastructure.html_parsers.base_parser import BaseHtmlTableParser


class Bs4HtmlTableParser(BaseHtmlTableParser):
    """Parse SAP HTML results table into DataFrame."""

    def parse(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        table = self._find_result_table(soup)
        if table is None:
            raise ParserError("No data table found in HTML")

        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                rows.append(cells)

        if not headers and rows:
            headers = rows.pop(0)

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows, columns=headers if headers else None)

    @staticmethod
    def _find_result_table(soup: BeautifulSoup):
        """Locate the correct results table using priority strategy."""
        # Priority 1: table inside #result div (SAP query results)
        result_div = soup.find("div", id="result")
        if result_div:
            table = result_div.find("table")
            if table is not None:
                return table

        # Priority 2: table with SearchResults class
        table = soup.find("table", class_="SearchResults")
        if table is not None:
            return table

        # Priority 3: first table that has <th> elements (likely data)
        for table in soup.find_all("table"):
            if table.find("th"):
                return table

        # Fallback: first table on the page
        return soup.find("table")
