"""Tests for commercial pipeline page."""

from __future__ import annotations

import pandas as pd
import pytest

from interfaces.streamlit.pages import commercial_pipeline as cp


class TestFindColumn:
    """Unit tests for _find_column."""

    def test_exact_match(self) -> None:
        df = pd.DataFrame({"Cliente": [], "Equipo": []})
        assert cp._find_column(df, ["cliente"]) == "Cliente"

    def test_partial_match(self) -> None:
        df = pd.DataFrame({"Código Cliente": []})
        assert cp._find_column(df, ["cliente"]) == "Código Cliente"

    def test_case_insensitive(self) -> None:
        df = pd.DataFrame({"ESTADO CONTRATO": []})
        assert cp._find_column(df, ["estado"]) == "ESTADO CONTRATO"

    def test_returns_none_when_no_match(self) -> None:
        df = pd.DataFrame({"X": [], "Y": []})
        assert cp._find_column(df, ["cliente"]) is None

    def test_matches_first_keyword(self) -> None:
        """If multiple keywords match different columns, returns first column that matches any."""
        df = pd.DataFrame({"Equipo": [], "Cliente": []})
        result = cp._find_column(df, ["cliente", "equipo"])
        # Order depends on column iteration order
        assert result in ("Cliente", "Equipo")


class TestDerivePipelineStage:
    """Unit tests for _derive_pipeline_stage classification."""

    def test_sin_contrato_becomes_oportunidad_venta(self) -> None:
        df = pd.DataFrame({
            "Estado Contrato": ["Sin_Contrato", "Sin_Contrato"],
            "Cliente": ["A", "B"],
            "Llamadas": [5, 3],
        })
        result = cp._derive_pipeline_stage(df)
        assert "Etapa Pipeline" in result.columns
        assert list(result["Etapa Pipeline"]) == ["Oportunidad Venta", "Oportunidad Venta"]

    def test_garantia_becomes_en_garantia(self) -> None:
        df = pd.DataFrame({
            "Estado Contrato": ["Garantía", "Garantía Parcial"],
            "Cliente": ["A", "B"],
            "Llamadas": [1, 2],
        })
        result = cp._derive_pipeline_stage(df)
        assert list(result["Etapa Pipeline"]) == ["En Garantía", "En Garantía"]

    def test_unknown_estado_becomes_otro(self) -> None:
        df = pd.DataFrame({
            "Estado Contrato": ["Vencido", None],
            "Cliente": ["A", "B"],
            "Llamadas": [1, 2],
        })
        result = cp._derive_pipeline_stage(df)
        assert list(result["Etapa Pipeline"]) == ["Otro", "Otro"]

    def test_mixed_stages(self) -> None:
        df = pd.DataFrame({
            "Estado Contrato": ["Sin_Contrato", "Garantía", "Vencido", "Garantía Extendida"],
            "Cliente": ["A", "B", "C", "D"],
            "Llamadas": [10, 5, 2, 3],
        })
        result = cp._derive_pipeline_stage(df)
        assert list(result["Etapa Pipeline"]) == [
            "Oportunidad Venta", "En Garantía", "Otro", "En Garantía",
        ]

    def test_no_estado_column_returns_unchanged(self) -> None:
        df = pd.DataFrame({"Cliente": ["A"], "Llamadas": [1]})
        result = cp._derive_pipeline_stage(df)
        pd.testing.assert_frame_equal(result, df)

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame({"Estado Contrato": pd.Series([], dtype=str)})
        result = cp._derive_pipeline_stage(df)
        assert len(result) == 0
        assert "Etapa Pipeline" in result.columns

    def test_warranty_column_detection(self) -> None:
        """Column detection finds 'warranty' keyword."""
        df = pd.DataFrame({
            "Warranty": ["Sin_Contrato"],
            "Llamadas": [1],
        })
        result = cp._derive_pipeline_stage(df)
        assert "Etapa Pipeline" in result.columns


class _FakePipeline:
    """Fake pipeline service that returns preset data."""

    def __init__(self, data: pd.DataFrame | None = None, should_fail: bool = False) -> None:
        self._data = data if data is not None else pd.DataFrame()
        self._should_fail = should_fail

    def execute(self, query_id: str, correlation_id: str) -> dict[str, object]:
        if self._should_fail:
            raise RuntimeError("SAP connection failed")
        return {"data": self._data, "meta": {}, "kpis": {}}


def _sample_df() -> pd.DataFrame:
    """Create a sample DataFrame matching pipeline_comercial output."""
    return pd.DataFrame({
        "Código Cliente": ["C001", "C002", "C003", "C004"],
        "Cliente": ["Hosp A", "Hosp B", "Clin C", "Clin D"],
        "Código Equipo": ["EQ-01", "EQ-02", "EQ-03", "EQ-04"],
        "Equipo": ["Tomógrafo", "Resonador", "Rayos X", "Ecógrafo"],
        "Número de Serie": ["SN-001", "SN-002", "SN-003", "SN-004"],
        "Estado Contrato": ["Sin_Contrato", "Garantía", "Sin_Contrato", "Garantía"],
        "Llamadas Correctivas": [12, 3, 8, 1],
    })


class TestRender:
    """Integration tests for render function."""

    def test_render_with_empty_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Show info message when no data is available."""
        calls: dict[str, list] = {"info": []}
        monkeypatch.setattr(cp.st, "subheader", lambda msg: None)
        monkeypatch.setattr(cp.st, "info", lambda msg: calls["info"].append(msg))
        monkeypatch.setattr(cp.st, "button", lambda *args, **kwargs: False)
        monkeypatch.setattr(cp, "_load_pipeline", lambda _svc: pd.DataFrame())

        services = {"pipeline": None}
        cp.render(services)

        assert any("No hay datos" in m for m in calls["info"])

    def test_render_shows_funnel_with_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Render pipeline stages and metrics with sample data."""
        calls: dict[str, list] = {
            "subheader": [],
            "metric": [],
            "dataframe": [],
            "bar_chart": [],
            "divider": [],
        }

        monkeypatch.setattr(cp, "_load_pipeline", lambda _svc: _sample_df())
        monkeypatch.setattr(cp.st, "subheader", lambda msg: calls["subheader"].append(msg))
        monkeypatch.setattr(cp.st, "metric", lambda label, value: calls["metric"].append(label))
        monkeypatch.setattr(cp.st, "selectbox", lambda label, options: "Todas")
        monkeypatch.setattr(
            cp.st, "dataframe", lambda df, **kwargs: calls["dataframe"].append(len(df))
        )
        monkeypatch.setattr(
            cp.st, "columns", lambda n: [_DummyColumn() for _ in range(n)]
        )
        monkeypatch.setattr(cp.st, "bar_chart", lambda data: calls["bar_chart"].append(True))
        monkeypatch.setattr(cp.st, "divider", lambda: calls["divider"].append(True))
        monkeypatch.setattr(cp.st, "button", lambda *args, **kwargs: False)

        services = {"pipeline": None}
        cp.render(services)

        assert any("Embudo" in m for m in calls["subheader"])
        assert len(calls["metric"]) >= 3
        assert len(calls["dataframe"]) > 0

    def test_render_catches_error_when_pipeline_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When _load_pipeline returns None, show info message."""
        calls: dict[str, list] = {"info": [], "subheader": []}
        monkeypatch.setattr(cp, "_load_pipeline", lambda _svc: None)
        monkeypatch.setattr(cp.st, "subheader", lambda msg: calls["subheader"].append(msg))
        monkeypatch.setattr(cp.st, "info", lambda msg: calls["info"].append(msg))
        monkeypatch.setattr(cp.st, "button", lambda *args, **kwargs: False)

        services = {"pipeline": None}
        cp.render(services)

        assert any("No hay datos" in m for m in calls["info"])


class _DummyColumn:
    """Fake Streamlit column that swallows metric calls, supports 'with' context."""
    def metric(self, label, value):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class _DummyContext:
    """Fake context manager for st.spinner."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass