"""Use case: export query output as bytes for browser download."""

import pandas as pd
from domain.contracts.ports import DataExporterPort


class ExportDataUseCase:
    """Exports dataframe to CSV/XLSX bytes."""

    def __init__(self, exporter: DataExporterPort) -> None:
        self._exporter = exporter

    def to_csv(self, df: pd.DataFrame) -> bytes:
        return self._exporter.export_csv(df)

    def to_xlsx(self, df: pd.DataFrame) -> bytes:
        return self._exporter.export_xlsx(df)