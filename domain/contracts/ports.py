"""Ports/interfaces for application layer."""

from typing import Protocol
import pandas as pd


class SapQueryGateway(Protocol):
    """Gateway that executes query and returns DataFrame (async)."""

    async def run_query(
        self,
        query_id: str,
        sql_text: str,
        correlation_id: str,
        *,
        param_overrides: dict[int, str] | None = None,
    ) -> pd.DataFrame: ...


class QueryCatalogPort(Protocol):
    """Reads query metadata and SQL."""

    def get_query_sql(self, query_id: str) -> tuple[dict, str]: ...


class DataExporterPort(Protocol):
    """Exports DataFrame to bytes for browser download."""

    def export_csv(self, df: pd.DataFrame) -> bytes: ...

    def export_xlsx(self, df: pd.DataFrame) -> bytes: ...