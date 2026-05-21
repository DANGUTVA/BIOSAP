"""Use case: compute commercial recommendations from equipment KPIs."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from domain.models.commercial import CommercialKPIs, Recommendation


class ComputeRecommendationsUseCase:

    def execute(
        self,
        df_by_equipment: pd.DataFrame,
        kpis: CommercialKPIs,
    ) -> list[Recommendation]:
        if df_by_equipment is None or df_by_equipment.empty:
            return []

        col_estado_gar = _find_column(df_by_equipment, ["estado garantía", "estado", "warranty", "garantia"])
        col_venc_gar = _find_column(df_by_equipment, ["vencimiento garantía", "vencimiento", "venc", "garantia"])

        recommendations: list[Recommendation] = []

        for _idx, row in df_by_equipment.iterrows():
            equipo = str(row.get("Equipo", ""))
            serial = str(row.get("Número Serie", row.get("Número Serie", "")))
            cliente = str(row.get("Cliente", ""))
            mtbf = row.get("MTBF (días)", 0.0)
            riesgo = row.get("Riesgo", 0.0)
            cumplimiento_raw = row.get("Cumplimiento PM", 1.0)
            n_correctivos = int(row.get("Correctivos", 0) or 0)
            n_preventivos = int(row.get("Preventivos", 0) or 0)
            pm_esperados = float(row.get("PM Esperados", 0) or 0)

            try:
                mtbf_val = float(mtbf)
            except (ValueError, TypeError):
                mtbf_val = 0.0

            try:
                riesgo_val = float(riesgo)
            except (ValueError, TypeError):
                riesgo_val = 0.0

            try:
                cumplimiento_val = float(cumplimiento_raw)
            except (ValueError, TypeError):
                cumplimiento_val = 1.0

            # MTBF: requiere ≥2 correctivos para ser significativo
            if mtbf_val > 0 and mtbf_val < 60 and n_correctivos >= 2:
                recommendations.append(Recommendation(
                    equipo=equipo,
                    serial=serial,
                    cliente=cliente,
                    tipo="urgente",
                    mensaje=f"MTBF crítico ({mtbf_val:.0f} días). Renovar contrato urgente.",
                ))

            # Riesgo alto: requiere al menos 1 PM y 1 correctivo para evaluar
            if riesgo_val != float("inf") and riesgo_val > 3.0 and n_preventivos >= 1 and n_correctivos >= 1:
                recommendations.append(Recommendation(
                    equipo=equipo,
                    serial=serial,
                    cliente=cliente,
                    tipo="advertencia",
                    mensaje=f"Riesgo alto ({riesgo_val:.1f}). Priorizar mantenimiento preventivo.",
                ))

            # Sin PM: requiere al menos 1 correctivo (equipo activo sin mantenimiento)
            if riesgo_val == float("inf") and n_correctivos >= 1:
                recommendations.append(Recommendation(
                    equipo=equipo,
                    serial=serial,
                    cliente=cliente,
                    tipo="urgente",
                    mensaje="Sin PM registrado. Requiere plan de mantenimiento inmediato.",
                ))

            # Cumplimiento PM bajo: requiere PM esperados > 0 y al menos 1 PM o 1 correctivo
            if cumplimiento_val != float("inf") and cumplimiento_val < 0.5 and pm_esperados > 0 and (n_preventivos >= 1 or n_correctivos >= 1):
                recommendations.append(Recommendation(
                    equipo=equipo,
                    serial=serial,
                    cliente=cliente,
                    tipo="advertencia",
                    mensaje=f"Cumplimiento PM bajo ({cumplimiento_val:.0%}). Revisar planificación de mantenimiento.",
                ))

            if col_estado_gar and col_estado_gar in df_by_equipment.columns:
                estado_val = str(row.get(col_estado_gar, "")).strip().lower()
                if "vencida" in estado_val:
                    recommendations.append(Recommendation(
                        equipo=equipo,
                        serial=serial,
                        cliente=cliente,
                        tipo="oportunidad",
                        mensaje="Garantía vencida o próxima a vencer. Oportunidad de renovación.",
                    ))
                elif col_venc_gar and col_venc_gar in df_by_equipment.columns:
                    venc_raw = row.get(col_venc_gar)
                    venc_dt = pd.to_datetime(venc_raw, errors="coerce")
                    if pd.notna(venc_dt):
                        venc_date = venc_dt.date()
                        hoy = date.today()
                        limite = hoy + timedelta(days=30)
                        if hoy <= venc_date <= limite:
                            recommendations.append(Recommendation(
                                equipo=equipo,
                                serial=serial,
                                cliente=cliente,
                                tipo="oportunidad",
                                mensaje="Garantía vencida o próxima a vencer. Oportunidad de renovación.",
                            ))

        return recommendations


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find column by keywords, preferring exact name match then longest substring match."""
    keywords_lower = [kw.lower() for kw in keywords]
    # First pass: exact column name match (case-insensitive)
    for col in df.columns:
        if str(col).strip().lower() in keywords_lower:
            return col
    # Second pass: substring match, preferring longest keyword match
    best = None
    best_len = 0
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords_lower:
            if kw in col_lower and len(kw) > best_len:
                best = col
                best_len = len(kw)
    return best
