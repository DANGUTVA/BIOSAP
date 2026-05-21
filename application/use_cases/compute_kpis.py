"""Use case: compute KPI summary from DataFrame."""

import pandas as pd
from domain.models.kpi import KPIResult


class ComputeKpisUseCase:
    """Calculates basic KPI metrics."""

    def execute(self, df: pd.DataFrame) -> KPIResult:
        numeric_columns = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        return KPIResult(
            total_rows=len(df),
            numeric_columns=numeric_columns,
            null_cells=int(df.isna().sum().sum()),
        )
