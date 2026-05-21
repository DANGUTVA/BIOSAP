"""Commercial intelligence domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CommercialFilter:
    """Dynamic filters for commercial intelligence queries.

    All fields are optional — None means 'no filter' (show all).
    Filters are applied client-side after data is loaded from SAP.
    """

    division: str | None = None
    marca: str | None = None
    modelo: str | None = None
    cliente: str | None = None
    fecha_desde: date | None = None
    fecha_hasta: date | None = None


@dataclass(frozen=True)
class CommercialStats:
    """Aggregate commercial statistics computed from filtered data.

    Uses per-equipment pricing (CTR1.U_Monto) instead of global contract pricing.
    """

    precio_promedio: float
    precio_min: float
    precio_max: float
    correctivos_promedio: float
    pm_promedio: float


@dataclass(frozen=True)
class CommercialKPIs:
    """Key Performance Indicators for commercial intelligence.

    - mtbf_dias: Mean Time Between Failures (days between corrective calls).
      0.0 means insufficient data (≤1 corrective call).
    - pm_anual: Preventive maintenances per year per equipment.
      0.0 means no PM records.
    - pm_esperados: Expected PMs per year based on periodicidad (12 / periodicidad).
      0.0 when no periodicidad data available.
    - cumplimiento_pm: PM realizados / PM esperados. 1.0 = on target, >1 = over-maintained.
      float('inf') when pm_esperados=0.
    - riesgo: Corrective / max(pm_realizados, 1). float('inf') when no data.
    - precio_sugerido: Suggested price based on per-equipment contract average (CTR1.U_Monto).
      0.0 when no pricing data available.
    """

    mtbf_dias: float
    pm_anual: float
    pm_esperados: float
    cumplimiento_pm: float
    riesgo: float
    precio_sugerido: float


@dataclass(frozen=True)
class Recommendation:
    """A single commercial recommendation based on KPI thresholds."""

    equipo: str
    serial: str
    cliente: str
    tipo: str  # "urgente", "advertencia", "oportunidad"
    mensaje: str