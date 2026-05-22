"""Tests for PandasExporter and ExportDataUseCase — bytes-based export."""

import io
import pandas as pd
import pytest

from infrastructure.exporters import PandasExporter
from application.use_cases.export_data import ExportDataUseCase


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({"nombre": ["Ana", "Luis"], "edad": [30, 25]})


@pytest.fixture()
def exporter() -> PandasExporter:
    return PandasExporter()


@pytest.fixture()
def use_case() -> ExportDataUseCase:
    return ExportDataUseCase(PandasExporter())


# ── PandasExporter ──────────────────────────────────────────────────


class TestPandasExporterCSV:
    def test_returns_bytes(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_csv(sample_df)
        assert isinstance(result, bytes)

    def test_csv_content_parseable(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_csv(sample_df)
        df_back = pd.read_csv(io.BytesIO(result))
        assert len(df_back) == 2
        assert list(df_back.columns) == ["nombre", "edad"]

    def test_csv_no_index(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_csv(sample_df)
        first_line = result.decode("utf-8").split("\n")[0]
        assert first_line.strip() == "nombre,edad"

    def test_csv_preserves_values(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_csv(sample_df)
        df_back = pd.read_csv(io.BytesIO(result))
        assert df_back["nombre"].tolist() == ["Ana", "Luis"]
        assert df_back["edad"].tolist() == [30, 25]

    def test_csv_empty_dataframe(self, exporter: PandasExporter):
        empty = pd.DataFrame(columns=["a", "b"])
        result = exporter.export_csv(empty)
        assert isinstance(result, bytes)
        df_back = pd.read_csv(io.BytesIO(result))
        assert len(df_back) == 0
        assert list(df_back.columns) == ["a", "b"]


class TestPandasExporterXLSX:
    def test_returns_bytes(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_xlsx(sample_df)
        assert isinstance(result, bytes)

    def test_xlsx_content_parseable(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_xlsx(sample_df)
        df_back = pd.read_excel(io.BytesIO(result), engine="openpyxl")
        assert len(df_back) == 2
        assert list(df_back.columns) == ["nombre", "edad"]

    def test_xlsx_preserves_values(self, exporter: PandasExporter, sample_df: pd.DataFrame):
        result = exporter.export_xlsx(sample_df)
        df_back = pd.read_excel(io.BytesIO(result), engine="openpyxl")
        assert df_back["nombre"].tolist() == ["Ana", "Luis"]
        assert df_back["edad"].tolist() == [30, 25]

    def test_xlsx_empty_dataframe(self, exporter: PandasExporter):
        empty = pd.DataFrame(columns=["a", "b"])
        result = exporter.export_xlsx(empty)
        assert isinstance(result, bytes)
        df_back = pd.read_excel(io.BytesIO(result), engine="openpyxl")
        assert len(df_back) == 0


# ── ExportDataUseCase ────────────────────────────────────────────────


class TestExportDataUseCase:
    def test_to_csv_delegates(self, use_case: ExportDataUseCase, sample_df: pd.DataFrame):
        result = use_case.to_csv(sample_df)
        assert isinstance(result, bytes)
        df_back = pd.read_csv(io.BytesIO(result))
        assert len(df_back) == 2

    def test_to_xlsx_delegates(self, use_case: ExportDataUseCase, sample_df: pd.DataFrame):
        result = use_case.to_xlsx(sample_df)
        assert isinstance(result, bytes)
        df_back = pd.read_excel(io.BytesIO(result), engine="openpyxl")
        assert len(df_back) == 2

    def test_to_csv_no_file_written(self, use_case: ExportDataUseCase, sample_df: pd.DataFrame):
        """Verify that no files are written to disk."""
        import os
        before = set(os.listdir(".")) if os.path.exists(".") else set()
        use_case.to_csv(sample_df)
        after = set(os.listdir(".")) if os.path.exists(".") else set()
        assert before == after  # No new files created

    def test_to_xlsx_no_file_written(self, use_case: ExportDataUseCase, sample_df: pd.DataFrame):
        """Verify that no files are written to disk."""
        import os
        before = set(os.listdir(".")) if os.path.exists(".") else set()
        use_case.to_xlsx(sample_df)
        after = set(os.listdir(".")) if os.path.exists(".") else set()
        assert before == after  # No new files created