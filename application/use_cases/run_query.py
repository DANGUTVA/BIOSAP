"""Use case: run SAP query."""

import asyncio
import pandas as pd
from domain.contracts.ports import QueryCatalogPort, SapQueryGateway


class RunQueryUseCase:
    """Resolve SQL from catalog and execute SAP query."""

    def __init__(self, catalog: QueryCatalogPort, gateway: SapQueryGateway) -> None:
        self._catalog = catalog
        self._gateway = gateway

    def execute(
        self,
        query_id: str,
        correlation_id: str,
        *,
        param_overrides: dict[int, str] | None = None,
    ) -> tuple[dict, pd.DataFrame]:
        meta, sql_text = self._catalog.get_query_sql(query_id)
        df = asyncio.run(
            self._gateway.run_query(
                query_id=query_id,
                sql_text=sql_text,
                correlation_id=correlation_id,
                param_overrides=param_overrides,
            )
        )
        return meta, df
