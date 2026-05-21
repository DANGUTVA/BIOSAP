"""Use case: end-to-end pipeline for query + enrichments."""

import pandas as pd
from application.use_cases.run_query import RunQueryUseCase
from application.use_cases.compute_kpis import ComputeKpisUseCase


class PipelineUseCase:
    """Run query and derive KPI bundle in one call."""

    def __init__(self, run_query: RunQueryUseCase, compute_kpis: ComputeKpisUseCase) -> None:
        self._run_query = run_query
        self._compute_kpis = compute_kpis

    def execute(
        self,
        query_id: str,
        correlation_id: str,
        *,
        param_overrides: dict[int, str] | None = None,
    ) -> dict[str, object]:
        meta, df = self._run_query.execute(
            query_id=query_id,
            correlation_id=correlation_id,
            param_overrides=param_overrides,
        )
        kpis = self._compute_kpis.execute(df)
        return {"meta": meta, "data": df, "kpis": kpis}
