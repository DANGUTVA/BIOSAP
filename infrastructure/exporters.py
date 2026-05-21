"""Data export adapters."""

from pathlib import Path
import pandas as pd


class PandasExporter:
    """Exports DataFrame to CSV and XLSX."""

    def export_csv(self, df: pd.DataFrame, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target, index=False)
        return target

    def export_xlsx(self, df: pd.DataFrame, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(target, index=False)
        return target
