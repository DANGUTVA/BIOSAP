"""Tests for commercial intelligence: KPIs, stats, recommendations, and filtering."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from domain.models.commercial import CommercialFilter, CommercialKPIs, CommercialStats, Recommendation
from application.use_cases.compute_commercial_kpis import ComputeCommercialKpisUseCase
from application.use_cases.compute_recommendations import ComputeRecommendationsUseCase
from application.use_cases.commercial_intelligence import CommercialIntelligenceUseCase


# ── Fixtures ──────────────────────────────────────────────────────


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _sample_contract_df() -> pd.DataFrame:
    """Realistic commercial intelligence data with mixed PM/corrective calls."""
    return _make_df([
        # GE OPTIMA CT540 - 2 preventivos, 1 correctivo, MTBF from 1 corrective = 0 (need >1)
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "OPTIMA CT540",
         "Número Serie": "650017", "Código Cliente": "C10001", "Cliente": "Hospital Calderón Guardia",
         "Ubicación": "San José", "Tipo Contrato": "Preventivo", "Monto Equipo": 5400.0,
         "Inicio Contrato": "2024-01-15", "Fin Contrato": "2025-01-15",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-06-30",
         "Tipo Llamada": 1, "Fecha Llamada": "2024-03-10"},
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "OPTIMA CT540",
         "Número Serie": "650017", "Código Cliente": "C10001", "Cliente": "Hospital Calderón Guardia",
         "Ubicación": "San José", "Tipo Contrato": "Preventivo", "Monto Equipo": 5400.0,
         "Inicio Contrato": "2024-01-15", "Fin Contrato": "2025-01-15",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-06-30",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-06-22"},
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "OPTIMA CT540",
         "Número Serie": "650017", "Código Cliente": "C10001", "Cliente": "Hospital Calderón Guardia",
         "Ubicación": "San José", "Tipo Contrato": "Preventivo", "Monto Equipo": 5400.0,
         "Inicio Contrato": "2024-01-15", "Fin Contrato": "2025-01-15",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-06-30",
         "Tipo Llamada": 1, "Fecha Llamada": "2024-09-05"},
        # Philips Ingenia - 2 PM, 2 correctivos → can compute MTBF
        {"División": "Imágenes Médicas", "Marca": "Philips", "Modelo": "Ingenia Ambition 1.5T",
         "Número Serie": "770025", "Código Cliente": "C10002", "Cliente": "Clínica Bíblica",
         "Ubicación": "Heredia", "Tipo Contrato": "Preventivo", "Monto Equipo": 8200.0,
         "Inicio Contrato": "2023-06-01", "Fin Contrato": "2024-06-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2024-12-15",
         "Tipo Llamada": 1, "Fecha Llamada": "2023-08-20"},
        {"División": "Imágenes Médicas", "Marca": "Philips", "Modelo": "Ingenia Ambition 1.5T",
         "Número Serie": "770025", "Código Cliente": "C10002", "Cliente": "Clínica Bíblica",
         "Ubicación": "Heredia", "Tipo Contrato": "Preventivo", "Monto Equipo": 8200.0,
         "Inicio Contrato": "2023-06-01", "Fin Contrato": "2024-06-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2024-12-15",
         "Tipo Llamada": 2, "Fecha Llamada": "2023-11-05"},
        {"División": "Imágenes Médicas", "Marca": "Philips", "Modelo": "Ingenia Ambition 1.5T",
         "Número Serie": "770025", "Código Cliente": "C10002", "Cliente": "Clínica Bíblica",
         "Ubicación": "Heredia", "Tipo Contrato": "Preventivo", "Monto Equipo": 8200.0,
         "Inicio Contrato": "2023-06-01", "Fin Contrato": "2024-06-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2024-12-15",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-02-14"},
        {"División": "Imágenes Médicas", "Marca": "Philips", "Modelo": "Ingenia Ambition 1.5T",
         "Número Serie": "770025", "Código Cliente": "C10002", "Cliente": "Clínica Bíblica",
         "Ubicación": "Heredia", "Tipo Contrato": "Preventivo", "Monto Equipo": 8200.0,
         "Inicio Contrato": "2023-06-01", "Fin Contrato": "2024-06-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2024-12-15",
         "Tipo Llamada": 1, "Fecha Llamada": "2024-05-30"},
        # Siemens SOMATOM - 2 PM, 2 correctivos, expired warranty
        {"División": "Imágenes Médicas", "Marca": "Siemens", "Modelo": "SOMATOM X.cite",
         "Número Serie": "880033", "Código Cliente": "C10003", "Cliente": "Hospital México",
         "Ubicación": "Alajuela", "Tipo Contrato": "Correctivo", "Monto Equipo": 3200.0,
         "Inicio Contrato": "2024-03-01", "Fin Contrato": "2025-03-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-09-20",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-04-15"},
        {"División": "Imágenes Médicas", "Marca": "Siemens", "Modelo": "SOMATOM X.cite",
         "Número Serie": "880033", "Código Cliente": "C10003", "Cliente": "Hospital México",
         "Ubicación": "Alajuela", "Tipo Contrato": "Correctivo", "Monto Equipo": 3200.0,
         "Inicio Contrato": "2024-03-01", "Fin Contrato": "2025-03-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-09-20",
         "Tipo Llamada": 1, "Fecha Llamada": "2024-06-10"},
        {"División": "Imágenes Médicas", "Marca": "Siemens", "Modelo": "SOMATOM X.cite",
         "Número Serie": "880033", "Código Cliente": "C10003", "Cliente": "Hospital México",
         "Ubicación": "Alajuela", "Tipo Contrato": "Correctivo", "Monto Equipo": 3200.0,
         "Inicio Contrato": "2024-03-01", "Fin Contrato": "2025-03-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-09-20",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-07-28"},
        {"División": "Imágenes Médicas", "Marca": "Siemens", "Modelo": "SOMATOM X.cite",
         "Número Serie": "880033", "Código Cliente": "C10003", "Cliente": "Hospital México",
         "Ubicación": "Alajuela", "Tipo Contrato": "Correctivo", "Monto Equipo": 3200.0,
         "Inicio Contrato": "2024-03-01", "Fin Contrato": "2025-03-01",
         "Estado Garantía": "En Garantía", "Vencimiento Garantía": "2025-09-20",
         "Tipo Llamada": 1, "Fecha Llamada": "2024-10-22"},
        # GE LOGIQ E10 - expired warranty
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "LOGIQ E10",
         "Número Serie": "650100", "Código Cliente": "C10004", "Cliente": "Hospital Nacional de Niños",
         "Ubicación": "Cartago", "Tipo Contrato": "Preventivo", "Monto Equipo": 4500.0,
         "Inicio Contrato": "2023-09-01", "Fin Contrato": "2024-09-01",
         "Estado Garantía": "Vencida", "Vencimiento Garantía": "2024-03-15",
         "Tipo Llamada": 1, "Fecha Llamada": "2023-10-15"},
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "LOGIQ E10",
         "Número Serie": "650100", "Código Cliente": "C10004", "Cliente": "Hospital Nacional de Niños",
         "Ubicación": "Cartago", "Tipo Contrato": "Preventivo", "Monto Equipo": 4500.0,
         "Inicio Contrato": "2023-09-01", "Fin Contrato": "2024-09-01",
         "Estado Garantía": "Vencida", "Vencimiento Garantía": "2024-03-15",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-01-08"},
        {"División": "Imágenes Médicas", "Marca": "GE", "Modelo": "LOGIQ E10",
         "Número Serie": "650100", "Código Cliente": "C10004", "Cliente": "Hospital Nacional de Niños",
         "Ubicación": "Cartago", "Tipo Contrato": "Preventivo", "Monto Equipo": 4500.0,
         "Inicio Contrato": "2023-09-01", "Fin Contrato": "2024-09-01",
         "Estado Garantía": "Vencida", "Vencimiento Garantía": "2024-03-15",
         "Tipo Llamada": 2, "Fecha Llamada": "2024-03-20"},
    ])


# ── ComputeCommercialKpisUseCase tests ──────────────────────────


class TestComputeStats:
    def test_stats_from_sample_data(self):
        df = _sample_contract_df()
        use_case = ComputeCommercialKpisUseCase()
        stats = use_case.compute_stats(df)
        assert isinstance(stats, CommercialStats)
        assert stats.precio_promedio > 0
        assert stats.precio_min <= stats.precio_promedio <= stats.precio_max
        assert stats.correctivos_promedio > 0
        assert stats.pm_promedio > 0

    def test_stats_empty_df(self):
        use_case = ComputeCommercialKpisUseCase()
        stats = use_case.compute_stats(pd.DataFrame())
        assert stats.precio_promedio == 0.0
        assert stats.precio_min == 0.0
        assert stats.precio_max == 0.0
        assert stats.correctivos_promedio == 0.0
        assert stats.pm_promedio == 0.0

    def test_stats_none_df(self):
        use_case = ComputeCommercialKpisUseCase()
        stats = use_case.compute_stats(None)
        assert stats.precio_promedio == 0.0

    def test_stats_only_correctivos(self):
        """When only corrective calls exist, PM average should be 0."""
        df = _make_df([
            {"Número Serie": "S1", "Tipo Llamada": 2, "Monto Equipo": 1000.0,
             "Fecha Llamada": "2024-01-01", "Marca": "X", "Modelo": "M1"},
        ])
        use_case = ComputeCommercialKpisUseCase()
        stats = use_case.compute_stats(df)
        assert stats.pm_promedio == 0.0
        assert stats.correctivos_promedio > 0


class TestComputeKpis:
    def test_kpis_from_sample_data(self):
        df = _sample_contract_df()
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(df)
        assert isinstance(kpis, CommercialKPIs)
        assert kpis.mtbf_dias > 0
        assert kpis.pm_anual > 0
        assert kpis.precio_sugerido > 0

    def test_kpis_empty_df(self):
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(pd.DataFrame())
        assert kpis.mtbf_dias == 0.0
        assert kpis.pm_anual == 0.0
        assert kpis.precio_sugerido == 0.0
        assert kpis.riesgo == float("inf")

    def test_kpis_none_df(self):
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(None)
        assert kpis.mtbf_dias == 0.0

    def test_mtbf_with_multiple_correctivos(self):
        """Philips 770025 has 2 correctivos → MTBF = days between them / (2-1)."""
        df = _make_df([
            {"Número Serie": "S1", "Tipo Llamada": 2, "Monto Equipo": 1000.0,
             "Fecha Llamada": "2024-01-01", "Inicio Contrato": "2023-01-01",
             "Estado Garantía": "Vigente"},
            {"Número Serie": "S1", "Tipo Llamada": 2, "Monto Equipo": 1000.0,
             "Fecha Llamada": "2024-04-01", "Inicio Contrato": "2023-01-01",
             "Estado Garantía": "Vigente"},
        ])
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(df)
        # 91 days / (2-1) = 91 days MTBF
        assert kpis.mtbf_dias == 91.0

    def test_mtbf_single_correctivo_returns_zero(self):
        """Only 1 corrective → can't compute time between failures → 0."""
        df = _make_df([
            {"Número Serie": "S1", "Tipo Llamada": 2, "Monto Equipo": 1000.0,
             "Fecha Llamada": "2024-01-01"},
        ])
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(df)
        assert kpis.mtbf_dias == 0.0

    def test_riesgo_no_preventivos_returns_correctivos(self):
        """Riesgo = correctivos / max(pm_realizados, 1) → when PM=0, riesgo = correctivos."""
        df = _make_df([
            {"Número Serie": "S1", "Tipo Llamada": 2, "Monto Equipo": 1000.0,
             "Fecha Llamada": "2024-01-01"},
        ])
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(df)
        assert kpis.riesgo == 1.0

    def test_precio_sugerido_averages_contracts(self):
        """Precio sugerido = mean of Monto Anual for contracted equipment."""
        df = _make_df([
            {"Número Serie": "S1", "Monto Equipo": 1000.0, "Estado Garantía": "Vigente",
             "Tipo Llamada": 1, "Fecha Llamada": "2024-01-01"},
            {"Número Serie": "S2", "Monto Equipo": 2000.0, "Estado Garantía": "Vigente",
             "Tipo Llamada": 1, "Fecha Llamada": "2024-01-02"},
        ])
        use_case = ComputeCommercialKpisUseCase()
        kpis = use_case.compute_kpis(df)
        assert kpis.precio_sugerido == 1500.0


class TestComputeKpisByEquipment:
    def test_by_equipment_returns_dataframe(self):
        df = _sample_contract_df()
        use_case = ComputeCommercialKpisUseCase()
        result = use_case.compute_kpis_by_equipment(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        # Should have one row per serial number
        assert "Número Serie" in result.columns
        assert "MTBF (días)" in result.columns
        assert "PM Anual" in result.columns
        assert "Riesgo" in result.columns

    def test_by_equipment_empty_df(self):
        use_case = ComputeCommercialKpisUseCase()
        result = use_case.compute_kpis_by_equipment(pd.DataFrame())
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_by_equipment_none_df(self):
        use_case = ComputeCommercialKpisUseCase()
        result = use_case.compute_kpis_by_equipment(None)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ── ComputeRecommendationsUseCase tests ─────────────────────────


class TestRecommendations:
    def test_low_mtbf_triggers_urgent(self):
        """MTBF < 60 should trigger 'urgente' recommendation."""
        df_eq = _make_df([
            {"Equipo": "GE Scanner", "Número Serie": "S1", "Cliente": "Hospital X",
             "Monto Equipo": 5000.0, "MTBF (días)": 45.0, "PM Anual": 3.0,
             "Correctivos": 5, "Preventivos": 3, "Riesgo": 1.67, "Precio Sugerido": 5000.0},
        ])
        use_case = ComputeRecommendationsUseCase()
        kpis = CommercialKPIs(mtbf_dias=45.0, pm_anual=3.0, pm_esperados=4.0, cumplimiento_pm=0.75, riesgo=1.67, precio_sugerido=5000.0)
        recs = use_case.execute(df_eq, kpis)
        assert len(recs) >= 1
        assert any(r.tipo == "urgente" and "MTBF" in r.mensaje for r in recs)

    def test_high_riesgo_triggers_advertencia(self):
        """Riesgo > 3.0 should trigger 'advertencia' recommendation."""
        df_eq = _make_df([
            {"Equipo": "Siemens CT", "Número Serie": "S2", "Cliente": "Hospital Y",
             "Monto Equipo": 8000.0, "MTBF (días)": 120.0, "PM Anual": 1.0,
             "Correctivos": 4, "Preventivos": 1, "Riesgo": 4.0, "Precio Sugerido": 8000.0},
        ])
        use_case = ComputeRecommendationsUseCase()
        kpis = CommercialKPIs(mtbf_dias=120.0, pm_anual=1.0, pm_esperados=2.0, cumplimiento_pm=0.5, riesgo=4.0, precio_sugerido=8000.0)
        recs = use_case.execute(df_eq, kpis)
        assert any(r.tipo == "advertencia" and "Riesgo" in r.mensaje for r in recs)

    def test_no_pm_triggers_urgent(self):
        """Riesgo == inf (no PM) should trigger 'urgente' recommendation."""
        df_eq = _make_df([
            {"Equipo": "GE US", "Número Serie": "S3", "Cliente": "Hospital Z",
             "Monto Equipo": 3000.0, "MTBF (días)": 0.0, "PM Anual": 0.0,
             "Correctivos": 2, "Preventivos": 0, "Riesgo": float("inf"), "Precio Sugerido": 3000.0},
        ])
        use_case = ComputeRecommendationsUseCase()
        kpis = CommercialKPIs(mtbf_dias=0.0, pm_anual=0.0, pm_esperados=0.0, cumplimiento_pm=float("inf"), riesgo=float("inf"), precio_sugerido=3000.0)
        recs = use_case.execute(df_eq, kpis)
        assert any(r.tipo == "urgente" and "PM" in r.mensaje for r in recs)

    def test_expired_warranty_triggers_oportunidad(self):
        """Estado containing 'vencida' should trigger 'oportunidad' recommendation."""
        df_eq = _make_df([
            {"Equipo": "GE LOGIQ", "Número Serie": "S4", "Cliente": "Hospital W",
             "Monto Equipo": 4500.0, "MTBF (días)": 200.0, "PM Anual": 2.0,
             "Correctivos": 2, "Preventivos": 2, "Riesgo": 1.0, "Precio Sugerido": 4500.0,
             "Estado Garantía": "Vencida"},
        ])
        use_case = ComputeRecommendationsUseCase()
        kpis = CommercialKPIs(mtbf_dias=200.0, pm_anual=2.0, pm_esperados=4.0, cumplimiento_pm=0.5, riesgo=1.0, precio_sugerido=4500.0)
        recs = use_case.execute(df_eq, kpis)
        assert any(r.tipo == "oportunidad" for r in recs)

    def test_empty_df_no_recommendations(self):
        use_case = ComputeRecommendationsUseCase()
        kpis = CommercialKPIs(mtbf_dias=0.0, pm_anual=0.0, pm_esperados=0.0, cumplimiento_pm=float("inf"), riesgo=float("inf"), precio_sugerido=0.0)
        recs = use_case.execute(pd.DataFrame(), kpis)
        assert recs == []


# ── CommercialFilter tests ──────────────────────────────────────


class TestCommercialFilter:
    def test_filter_by_marca(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        filtros = CommercialFilter(marca="Philips")
        result = use_case._apply_filters(df, filtros)
        assert len(result) > 0
        assert all("philips" in str(m).lower() for m in result["Marca"])

    def test_filter_by_cliente(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        filtros = CommercialFilter(cliente="Bíblica")
        result = use_case._apply_filters(df, filtros)
        assert len(result) > 0
        assert all("bíblica" in str(c).lower() for c in result["Cliente"])

    def test_filter_by_fecha_desde(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        filtros = CommercialFilter(fecha_desde=date(2024, 6, 1))
        result = use_case._apply_filters(df, filtros)
        col_fecha = "Fecha Llamada"
        if col_fecha in result.columns:
            fechas = pd.to_datetime(result[col_fecha], errors="coerce")
            assert fechas.min() >= pd.Timestamp(date(2024, 6, 1))

    def test_filter_none_returns_all(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        result = use_case._apply_filters(df, None)
        assert len(result) == len(df)

    def test_filter_combined(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        filtros = CommercialFilter(marca="GE", cliente="Hospital")
        result = use_case._apply_filters(df, filtros)
        assert len(result) > 0
        assert all("ge" in str(m).lower() for m in result["Marca"])


# ── Integration: _merge_original_columns ────────────────────────


class TestMergeOriginalColumns:
    def test_merge_adds_warranty_columns(self):
        df = _sample_contract_df()
        use_case = CommercialIntelligenceUseCase(
            pipeline=None,  # type: ignore
            compute_kpis=ComputeCommercialKpisUseCase(),
            compute_recommendations=ComputeRecommendationsUseCase(),
        )
        kpis_use_case = ComputeCommercialKpisUseCase()
        by_equipment = kpis_use_case.compute_kpis_by_equipment(df)
        merged = use_case._merge_original_columns(df, by_equipment)
        assert "Estado Garantía" in merged.columns