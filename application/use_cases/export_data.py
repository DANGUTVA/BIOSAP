"""Use case: export query output."""

from pathlib import Path
import pandas as pd
from domain.contracts.ports import DataExporterPort


class ExportDataUseCase:
    """Exports dataframe to csv/xlsx."""

    def __init__(self, exporter: DataExporterPort) -> None:
        self._exporter = exporter

    def to_csv(self, df: pd.DataFrame, target: Path) -> Path:
        return self._exporter.export_csv(df, target)

    def to_xlsx(self, df: pd.DataFrame, target: Path) -> Path:
        return self._exporter.export_xlsx(df, target)
