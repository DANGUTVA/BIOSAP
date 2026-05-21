"""Use case: orchestrate commercial intelligence pipeline.

Strategy: Load data from TWO simple SAP queries (no heavy JOINs) and merge
client-side in Python:
1. llamadas_servicio_division — FA_OSCL all calls (PM + corrective) with Marca, Modelo, Fecha
2. contratos_biomedicos — OCTR+CTR1+OITM contracts with pricing, locations, dates
3. garantias_90_dias — warranty expiration data (optional enrichment)

These queries are each simple enough to run within SAP's 90s timeout.
The merge matches service calls with contracts by Número Serie / manufSN.
"""

from __future__ import annotations

import pandas as pd

from domain.models.commercial import CommercialFilter, CommercialKPIs, CommercialStats, Recommendation
from application.use_cases.compute_commercial_kpis import ComputeCommercialKpisUseCase
from application.use_cases.compute_recommendations import ComputeRecommendationsUseCase
from application.use_cases.pipeline import PipelineUseCase


def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Find column by keywords, preferring exact name match then longest substring match."""
    keywords_lower = [kw.lower() for kw in keywords]
    for col in df.columns:
        if str(col).strip().lower() in keywords_lower:
            return col
    best = None
    best_len = 0
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords_lower:
            if kw in col_lower and len(kw) > best_len:
                best = col
                best_len = len(kw)
    return best


def _normalize_serial(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize serial number columns to a single 'Número Serie' column.
    
    Different queries use different column names:
    - 'Número de Serie' (llamadas_correctivas_division)
    - 'Número Serie' (contratos_biomedicos, llamadas_servicio_division)
    - 'manufSN' (raw SAP)
    """
    df = df.copy()
    serial_col = _find_column(df, ["número serie", "número de serie", "serial", "manufsn"])
    if serial_col and serial_col != "Número Serie":
        df["Número Serie"] = df[serial_col].astype(str).str.strip()
    elif "Número Serie" not in df.columns:
        # Fallback: create empty
        df["Número Serie"] = ""
    return df


class CommercialIntelligenceUseCase:

    def __init__(
        self,
        pipeline: PipelineUseCase,
        compute_kpis: ComputeCommercialKpisUseCase,
        compute_recommendations: ComputeRecommendationsUseCase,
    ) -> None:
        self._pipeline = pipeline
        self._compute_kpis = compute_kpis
        self._compute_recommendations = compute_recommendations

    def execute(
        self,
        *,
        division: str = "Imágenes Médicas",
        filtros: CommercialFilter | None = None,
    ) -> dict:
        # 1. Load ALL service calls (PM + corrective) with Marca, Modelo, Fecha
        # Division is hardcoded in SQL (no [%0] parameter) to avoid SAP timeout
        df_calls = self._load_query(
            query_id="llamadas_servicio_division",
            correlation_id="commercial-servicio",
            param_overrides=None,
            cache_key=f"df_servicio_{division}",
        )

        # 2. Load contracts with pricing and locations
        # Division is hardcoded in SQL (no [%0] parameter) to avoid SAP timeout
        df_contratos = self._load_query(
            query_id="contratos_biomedicos",
            correlation_id="commercial-contratos",
            param_overrides=None,
            cache_key=f"df_contratos_{division}",
        )

        # 3. Merge calls with contract data by serial number
        df_merged = self._merge_calls_with_contracts(df_calls, df_contratos)

        if df_merged.empty:
            empty_stats = CommercialStats(
                precio_promedio=0.0, precio_min=0.0, precio_max=0.0,
                correctivos_promedio=0.0, pm_promedio=0.0,
            )
            empty_kpis = CommercialKPIs(
                mtbf_dias=0.0, pm_anual=0.0, pm_esperados=0.0,
                cumplimiento_pm=float("inf"), riesgo=float("inf"), precio_sugerido=0.0,
            )
            return {
                "data": df_merged,
                "stats": empty_stats,
                "kpis": empty_kpis,
                "by_equipment": pd.DataFrame(),
                "recommendations": [],
            }

        # 4. Apply client-side filters
        df_filtered = self._apply_filters(df_merged, filtros)

        # 5. Compute metrics on filtered data
        stats = self._compute_kpis.compute_stats(df_filtered)
        kpis = self._compute_kpis.compute_kpis(df_filtered)
        by_equipment = self._compute_kpis.compute_kpis_by_equipment(df_filtered)

        merged = self._merge_original_columns(df_filtered, by_equipment)
        recommendations = self._compute_recommendations.execute(merged, kpis)

        return {
            "data": df_filtered,
            "stats": stats,
            "kpis": kpis,
            "by_equipment": by_equipment,
            "recommendations": recommendations,
        }

    def _load_query(
        self,
        query_id: str,
        correlation_id: str,
        param_overrides: dict | None,
        cache_key: str,
    ) -> pd.DataFrame:
        """Load a query via pipeline, returning empty DataFrame on failure."""
        try:
            result = self._pipeline.execute(
                query_id=query_id,
                correlation_id=correlation_id,
                param_overrides=param_overrides,
            )
            df = result.get("data")
            if df is not None and not df.empty:
                return _normalize_serial(df)
        except Exception:
            pass
        return pd.DataFrame()

    def _merge_calls_with_contracts(
        self,
        df_calls: pd.DataFrame,
        df_contratos: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge service call data with contract data by Número Serie.
        
        Service calls provide: Marca, Modelo, Tipo Llamada, Fecha Llamada, Estado Garantía
        Contracts provide: Monto Equipo, Periodicidad, Moneda, Renovación, Tipo Contrato,
                           Ubicación, Inicio/Fin Contrato
        """
        if df_calls.empty and df_contratos.empty:
            return pd.DataFrame()

        # If we only have calls (no contracts), return calls as-is
        if df_contratos.empty:
            return df_calls

        # If we only have contracts (no calls), add Tipo Llamada=0
        if df_calls.empty:
            df_contratos = df_contratos.copy()
            df_contratos["Tipo Llamada"] = 0
            df_contratos["Fuente"] = "Contrato"
            return df_contratos

        # Both exist — merge contract fields onto calls
        serial_col = "Número Serie"
        
        # Extract contract-level columns (one per serial)
        contract_fields = []
        for col in df_contratos.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in [
                "monto equipo", "monto", "periodicidad", "moneda",
                "renovación", "tipo contrato", "ubicación", "inicio", "fin",
            ]):
                contract_fields.append(col)

        # Ensure Marca is always included
        marca_col = _find_column(df_contratos, ["marca", "manufacturer"])
        if marca_col and marca_col not in contract_fields:
            contract_fields.append(marca_col)

        # Build a contract lookup by serial number
        all_fields = [serial_col] + [c for c in contract_fields if c in df_contratos.columns and c != serial_col]
        all_fields_unique = list(dict.fromkeys(all_fields))  # remove duplicates preserving order
        
        df_contrato_lookup = df_contratos[all_fields_unique].drop_duplicates(subset=[serial_col])

        # Merge onto calls
        df_merged = df_calls.merge(df_contrato_lookup, on=serial_col, how="left")

        # Clean up duplicate columns from merge (_x from calls, _y from contracts)
        # Prefer the call-level data for shared columns
        rename_map = {}
        cols_to_drop = []
        for col in df_merged.columns:
            if col.endswith("_x"):
                base = col[:-2]
                col_y = f"{base}_y"
                if col_y in df_merged.columns:
                    # Keep x (call-level) as the authoritative value, drop y
                    rename_map[col] = base
                    cols_to_drop.append(col_y)
                else:
                    rename_map[col] = base
            elif col.endswith("_y") and col not in cols_to_drop:
                # Standalone _y column (contract data not in calls)
                rename_map[col] = col[:-2]

        df_merged = df_merged.rename(columns=rename_map)
        df_merged = df_merged.drop(columns=cols_to_drop, errors="ignore")

        return df_merged

    def _apply_filters(
        self, df: pd.DataFrame, filtros: CommercialFilter | None
    ) -> pd.DataFrame:
        if filtros is None:
            return df
        result = df.copy()

        if filtros.marca:
            col = _find_column(result, ["marca", "manufacturer", "brand"])
            if col:
                result = result[result[col].astype(str).str.contains(
                    filtros.marca, case=False, na=False, regex=False
                )]

        if filtros.modelo:
            col = _find_column(result, ["modelo", "model"])
            if col:
                result = result[result[col].astype(str).str.contains(
                    filtros.modelo, case=False, na=False, regex=False
                )]

        if filtros.cliente:
            col = _find_column(result, ["cliente", "cardname", "customer"])
            if col:
                result = result[result[col].astype(str).str.contains(
                    filtros.cliente, case=False, na=False, regex=False
                )]

        if filtros.fecha_desde:
            col = _find_column(result, ["fecha llamada", "fecha", "call date"])
            if col:
                fechas = pd.to_datetime(result[col], errors="coerce")
                desde = pd.Timestamp(filtros.fecha_desde)
                result = result[fechas >= desde]

        if filtros.fecha_hasta:
            col = _find_column(result, ["fecha llamada", "fecha", "call date"])
            if col:
                fechas = pd.to_datetime(result[col], errors="coerce")
                hasta = pd.Timestamp(filtros.fecha_hasta)
                result = result[fechas <= hasta]

        return result

    def _merge_original_columns(
        self, original: pd.DataFrame, by_equipment: pd.DataFrame
    ) -> pd.DataFrame:
        if by_equipment.empty:
            return by_equipment

        col_serie_orig = _find_column(original, ["número serie", "serie", "serial"])
        col_estado_gar = _find_column(original, ["estado garantía", "estado", "warranty"])
        col_venc_gar = _find_column(original, ["vencimiento garantía", "vencimiento", "venc"])
        col_periodicidad = _find_column(original, ["periodicidad", "periodicidad", "frecuencia"])
        col_moneda = _find_column(original, ["moneda", "currency"])
        col_renovacion = _find_column(original, ["renovación", "renovacion", "renewal"])

        merge_cols_orig: list[str] = []
        rename_map: dict[str, str] = {}

        if col_estado_gar and col_estado_gar in original.columns:
            merge_cols_orig.append(col_estado_gar)
            rename_map[col_estado_gar] = "Estado Garantía"

        if col_venc_gar and col_venc_gar in original.columns:
            merge_cols_orig.append(col_venc_gar)
            rename_map[col_venc_gar] = "Vencimiento Garantía"

        if col_periodicidad and col_periodicidad in original.columns:
            merge_cols_orig.append(col_periodicidad)
            rename_map[col_periodicidad] = "Periodicidad"

        if col_moneda and col_moneda in original.columns:
            merge_cols_orig.append(col_moneda)
            rename_map[col_moneda] = "Moneda"

        if col_renovacion and col_renovacion in original.columns:
            merge_cols_orig.append(col_renovacion)
            rename_map[col_renovacion] = "Renovación"

        if not merge_cols_orig or not col_serie_orig:
            return by_equipment

        eq_serial_col = "Número Serie"
        if eq_serial_col not in by_equipment.columns:
            return by_equipment

        first_per_serie = original.drop_duplicates(subset=[col_serie_orig])[[col_serie_orig] + merge_cols_orig].copy()
        first_per_serie = first_per_serie.rename(columns=rename_map)

        merged = by_equipment.merge(first_per_serie, left_on=eq_serial_col, right_on=col_serie_orig, how="left")
        # Only drop right-side key if it's different from left-side key
        if col_serie_orig != eq_serial_col:
            merged = merged.drop(columns=[col_serie_orig], errors="ignore")
        return merged
