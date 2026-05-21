"""Base HTML parser contract."""

from abc import ABC, abstractmethod
import pandas as pd


class BaseHtmlTableParser(ABC):
    """Parse an HTML table to DataFrame."""

    @abstractmethod
    def parse(self, html: str) -> pd.DataFrame:
        """Parse table html."""
