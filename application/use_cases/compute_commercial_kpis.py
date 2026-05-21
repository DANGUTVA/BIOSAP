"""Use case: compute commercial KPIs and stats from equipment data."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from domain.models.commercial import CommercialKPIs, CommercialStats


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find column by keywords, preferring exact name match then longest substring match."""
    keywords_lower = [kw.lower() for kw in keywords]
    # First pass: exact column name match (case-insensitive)
    for col in df.columns:
        if str(col).strip().lower() in keywords_lower:
            return col
    # Second pass: substring match, preferring longest keyword match for specificity
    best = None
    best_len = 0
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords_lower:
            if kw in col_lower and len(kw) > best_len:
                best = col
                best_len = len(kw)
    return best


def _parse_sap_number(series: pd.Series) -> pd.Series:
    """Convert SAP European number format (1 234,56) to float Series."""
    cleaned = series.astype(str).str.replace("\xa0", "", regex=False)
    cleaned = cleaned.str.replace(" ", "", regex=False)
    has_trailing_minus = cleaned.str.endswith("-")
    cleaned = cleaned.str.rstrip("-")
    cleaned = cleaned.str.replace(",", ".", regex=False)
    result = pd.to_numeric(cleaned, errors="coerce")
    result[has_trailing_minus] = -result[has_trailing_minus].abs()
    return result


def _parse_sap_number_scalar(val) -> float:
    """Parse a single SAP European-format number string to float."""
    if val is None:
        return 0.0
    try:
        if not isinstance(val, str) and pd.isna(val):
            return 0.0
    except Exception:
        pass
    cleaned = str(val).replace("\xa0", "").replace(" ", "")
    is_negative = cleaned.endswith("-")
    cleaned = cleaned.rstrip("-")
    cleaned = cleaned.replace(",", ".")
    try:
        result = float(cleaned)
        return -result if is_negative else result
    except (ValueError, TypeError):
        return 0.0


class ComputeCommercialKpisUseCase:

    def compute_stats(self, df: pd.DataFrame) -> CommercialStats:
        if df is None or df.empty:
            return CommercialStats(
                precio_promedio=0.0,
                precio_min=0.0,
                precio_max=0.0,
                correctivos_promedio=0.0,
                pm_promedio=0.0,
            )

        col_monto = _find_column(df, ["monto equipo", "monto", "precio"])
        col_tipo = _find_column(df, ["tipo llamada", "call type", "tipo_llamada"])
        col_serie = _find_column(df, ["número serie", "serie", "serial"])

        if col_monto:
            monto = _parse_sap_number(df[col_monto])
            # Exclude zero/NaN values so stats reflect actual contract amounts
            monto_valid = monto[monto > 0]
            precio_promedio = float(monto_valid.mean()) if monto_valid.notna().any() else 0.0
            precio_min = float(monto_valid.min()) if monto_valid.notna().any() else 0.0
            precio_max = float(monto_valid.max()) if monto_valid.notna().any() else 0.0
        else:
            precio_promedio = 0.0
            precio_min = 0.0
            precio_max = 0.0

        if col_tipo and col_serie:
            correctivos = df[df[col_tipo].astype(str) == "2"]
            preventivos = df[df[col_tipo].astype(str) == "1"]

            if correctivos.empty:
                correctivos_promedio = 0.0
            else:
                counts = correctivos.groupby(col_serie).size()
                correctivos_promedio = float(counts.mean())

            if preventivos.empty:
                pm_promedio = 0.0
            else:
                counts = preventivos.groupby(col_serie).size()
                pm_promedio = float(counts.mean())
        else:
            correctivos_promedio = 0.0
            pm_promedio = 0.0

        return CommercialStats(
            precio_promedio=precio_promedio,
            precio_min=precio_min,
            precio_max=precio_max,
            correctivos_promedio=correctivos_promedio,
            pm_promedio=pm_promedio,
        )

    def compute_kpis(self, df: pd.DataFrame) -> CommercialKPIs:
        if df is None or df.empty:
            return CommercialKPIs(
                mtbf_dias=0.0,
                pm_anual=0.0,
                pm_esperados=0.0,
                cumplimiento_pm=float("inf"),
                riesgo=float("inf"),
                precio_sugerido=0.0,
            )

        col_tipo = _find_column(df, ["tipo llamada", "call type", "tipo_llamada"])
        col_serie = _find_column(df, ["número serie", "serie", "serial"])
        col_fecha = _find_column(df, ["fecha llamada", "fecha", "call date"])
        col_inicio = _find_column(df, ["inicio contrato", "inicio", "start date"])
        col_monto = _find_column(df, ["monto equipo", "monto", "precio"])
        col_estado = _find_column(df, ["estado garantía", "estado", "warranty"])
        col_periodicidad = _find_column(df, ["periodicidad", "periodicidad", "frecuencia"])

        mtbf_dias = self._compute_mtbf(df, col_tipo, col_serie, col_fecha)
        pm_anual = self._compute_pm_anual(df, col_tipo, col_serie, col_inicio)
        pm_esperados = self._compute_pm_esperados(df, col_periodicidad, col_serie)
        cumplimiento_pm = self._compute_cumplimiento_pm(pm_anual, pm_esperados)
        riesgo = self._compute_riesgo(df, col_tipo)
        precio_sugerido = self._compute_precio_sugerido(df, col_monto, col_estado)

        return CommercialKPIs(
            mtbf_dias=mtbf_dias,
            pm_anual=pm_anual,
            pm_esperados=pm_esperados,
            cumplimiento_pm=cumplimiento_pm,
            riesgo=riesgo,
            precio_sugerido=precio_sugerido,
        )

    def _compute_mtbf(
        self,
        df: pd.DataFrame,
        col_tipo: str | None,
        col_serie: str | None,
        col_fecha: str | None,
    ) -> float:
        if not col_tipo or not col_serie or not col_fecha:
            return 0.0

        correctivos = df[df[col_tipo].astype(str) == "2"].copy()
        if correctivos.empty:
            return 0.0

        correctivos.loc[:, "_fecha"] = pd.to_datetime(
            correctivos[col_fecha], errors="coerce"
        )
        correctivos = correctivos.dropna(subset=["_fecha"])

        mtbf_per_equipment: list[float] = []
        for _serie, group in correctivos.groupby(col_serie):
            group = group.sort_values("_fecha")
            n = len(group)
            if n <= 1:
                continue
            first = group["_fecha"].iloc[0]
            last = group["_fecha"].iloc[-1]
            days = (last - first).days
            mtbf_equipment = days / (n - 1)
            if mtbf_equipment > 0:
                mtbf_per_equipment.append(mtbf_equipment)

        if not mtbf_per_equipment:
            return 0.0

        return float(pd.Series(mtbf_per_equipment).mean())

    def _compute_pm_anual(
        self,
        df: pd.DataFrame,
        col_tipo: str | None,
        col_serie: str | None,
        col_inicio: str | None,
    ) -> float:
        if not col_tipo or not col_serie:
            return 0.0

        preventivos = df[df[col_tipo].astype(str) == "1"]
        if preventivos.empty:
            return 0.0

        today = date.today()

        pm_per_year: list[float] = []
        for _serie, group in preventivos.groupby(col_serie):
            pm_count = len(group)
            if col_inicio and col_inicio in df.columns:
                inicio_val = group[col_inicio].iloc[0]
                inicio_dt = pd.to_datetime(inicio_val, errors="coerce")
                if pd.notna(inicio_dt):
                    years_active = (today - inicio_dt.date()).days / 365.25
                else:
                    years_active = 1.0
            else:
                years_active = 1.0

            years_active = max(years_active, 0.5)
            pm_per_year.append(pm_count / years_active)

        if not pm_per_year:
            return 0.0

        return float(pd.Series(pm_per_year).mean())

    def _compute_pm_esperados(
        self,
        df: pd.DataFrame,
        col_periodicidad: str | None,
        col_serie: str | None,
    ) -> float:
        if not col_periodicidad or not col_serie:
            return 0.0

        pm_per_equipment: list[float] = []
        for _serie, group in df.groupby(col_serie):
            periodicidad_raw = group[col_periodicidad].iloc[0]
            periodicidad = pd.to_numeric(periodicidad_raw, errors="coerce")
            if pd.notna(periodicidad) and periodicidad > 0:
                pm_per_equipment.append(12.0 / periodicidad)

        if not pm_per_equipment:
            return 0.0

        return float(pd.Series(pm_per_equipment).mean())

    def _compute_cumplimiento_pm(self, pm_anual: float, pm_esperados: float) -> float:
        if pm_esperados == 0.0 or pm_esperados == float("inf"):
            return float("inf")
        return pm_anual / pm_esperados

    def _compute_riesgo(
        self, df: pd.DataFrame, col_tipo: str | None
    ) -> float:
        if not col_tipo:
            return float("inf")

        total_correctivos = len(df[df[col_tipo].astype(str) == "2"])
        total_pm_realizados = len(df[df[col_tipo].astype(str) == "1"])

        return total_correctivos / max(total_pm_realizados, 1)

    def _compute_precio_sugerido(
        self,
        df: pd.DataFrame,
        col_monto: str | None,
        col_estado: str | None,
    ) -> float:
        if not col_monto:
            return 0.0

        if col_estado and col_estado in df.columns:
            con_contrato = df[df[col_estado].astype(str) != "Sin_Contrato"]
            if con_contrato.empty:
                con_contrato = df

            monto = _parse_sap_number(con_contrato[col_monto])
        else:
            monto = _parse_sap_number(df[col_monto])

        # Exclude zero values — they represent contracts without pricing
        monto_valid = monto[monto > 0]
        if monto_valid.notna().any():
            return float(monto_valid.mean())

        return 0.0

    def compute_kpis_by_equipment(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(
                columns=[
                    "Equipo",
                    "Número Serie",
                    "Cliente",
                    "Monto Equipo",
                    "MTBF (días)",
                    "PM Anual",
                    "Correctivos",
                    "Preventivos",
                    "Riesgo",
                    "Precio Sugerido",
                    "Periodicidad",
                    "PM Esperados",
                    "Cumplimiento PM",
                ]
            )

        col_tipo = _find_column(df, ["tipo llamada", "call type", "tipo_llamada"])
        col_serie = _find_column(df, ["número serie", "serie", "serial"])
        col_fecha = _find_column(df, ["fecha llamada", "fecha", "call date"])
        col_inicio = _find_column(df, ["inicio contrato", "inicio", "start date"])
        col_modelo = _find_column(df, ["modelo", "model", "equipo"])
        col_cliente = _find_column(df, ["cliente", "cardname", "customer"])
        col_monto = _find_column(df, ["monto equipo", "monto", "precio"])
        col_periodicidad = _find_column(df, ["periodicidad", "periodicidad", "frecuencia"])

        if not col_serie:
            return pd.DataFrame(
                columns=[
                    "Equipo",
                    "Número Serie",
                    "Cliente",
                    "Monto Equipo",
                    "MTBF (días)",
                    "PM Anual",
                    "Correctivos",
                    "Preventivos",
                    "Riesgo",
                    "Precio Sugerido",
                    "Periodicidad",
                    "PM Esperados",
                    "Cumplimiento PM",
                ]
            )

        today = date.today()
        rows: list[dict] = []

        for serie, group in df.groupby(col_serie):
            modelo = group[col_modelo].iloc[0] if col_modelo and col_modelo in group.columns else ""
            cliente = group[col_cliente].iloc[0] if col_cliente and col_cliente in group.columns else ""
            monto_val = _parse_sap_number_scalar(group[col_monto].iloc[0]) if col_monto and col_monto in group.columns else 0.0
            monto_final = float(monto_val)

            correctivos = group[group[col_tipo].astype(str) == "2"] if col_tipo else pd.DataFrame()
            preventivos = group[group[col_tipo].astype(str) == "1"] if col_tipo else pd.DataFrame()

            n_correctivos = len(correctivos)
            n_preventivos = len(preventivos)

            mtbf = 0.0
            if col_tipo and col_fecha and not correctivos.empty:
                corr_sorted = correctivos.copy()
                corr_sorted["_fecha"] = pd.to_datetime(corr_sorted[col_fecha], errors="coerce")
                corr_sorted = corr_sorted.dropna(subset=["_fecha"])
                corr_sorted = corr_sorted.sort_values("_fecha")
                n = len(corr_sorted)
                if n > 1:
                    first = corr_sorted["_fecha"].iloc[0]
                    last = corr_sorted["_fecha"].iloc[-1]
                    mtbf = (last - first).days / (n - 1)

            pm_anual = 0.0
            if col_tipo and n_preventivos > 0:
                years_active = 1.0
                if col_inicio and col_inicio in group.columns:
                    inicio_val = group[col_inicio].iloc[0]
                    inicio_dt = pd.to_datetime(inicio_val, errors="coerce")
                    if pd.notna(inicio_dt):
                        years_active = (today - inicio_dt.date()).days / 365.25
                years_active = max(years_active, 0.5)
                pm_anual = n_preventivos / years_active

            riesgo = n_correctivos / max(n_preventivos, 1)

            periodicidad_val = 0.0
            pm_esperados = float("inf")
            cumplimiento_pm = float("inf")

            if col_periodicidad and col_periodicidad in group.columns:
                periodicidad_raw = group[col_periodicidad].iloc[0]
                periodicidad_val = pd.to_numeric(periodicidad_raw, errors="coerce")
                if pd.isna(periodicidad_val):
                    periodicidad_val = 0.0
                else:
                    periodicidad_val = float(periodicidad_val)

                if periodicidad_val > 0:
                    pm_esperados = 12.0 / periodicidad_val
                    cumplimiento_pm = pm_anual / pm_esperados if pm_esperados > 0 else float("inf")

            rows.append({
                "Equipo": modelo,
                "Número Serie": serie,
                "Cliente": cliente,
                "Monto Equipo": monto_final,
                "MTBF (días)": mtbf,
                "PM Anual": pm_anual,
                "Correctivos": n_correctivos,
                "Preventivos": n_preventivos,
                "Riesgo": riesgo,
                "Precio Sugerido": monto_final,
                "Periodicidad": periodicidad_val,
                "PM Esperados": pm_esperados,
                "Cumplimiento PM": cumplimiento_pm,
            })

        return pd.DataFrame(rows)
