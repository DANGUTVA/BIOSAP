"""Data export adapters — generate bytes in memory for browser download."""

import io

import pandas as pd


class PandasExporter:
    """Exports DataFrame to CSV and XLSX bytes."""

    def export_csv(self, df: pd.DataFrame) -> bytes:
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return buf.getvalue()

    def export_xlsx(self, df: pd.DataFrame) -> bytes:
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return buf.getvalue()