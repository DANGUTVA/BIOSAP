"""KPI related domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KPIResult:
    """Simple KPI representation."""

    total_rows: int
    numeric_columns: list[str]
    null_cells: int
