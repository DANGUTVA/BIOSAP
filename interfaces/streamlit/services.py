"""Composition root for Streamlit pages."""

from app.config.settings import get_settings
from app.observability.logger import set_correlation_id
from application.use_cases.commercial_intelligence import CommercialIntelligenceUseCase
from application.use_cases.compute_commercial_kpis import ComputeCommercialKpisUseCase
from application.use_cases.compute_kpis import ComputeKpisUseCase
from application.use_cases.compute_recommendations import ComputeRecommendationsUseCase
from application.use_cases.export_data import ExportDataUseCase
from application.use_cases.pipeline import PipelineUseCase
from application.use_cases.run_query import RunQueryUseCase
from application.use_cases.search_data import SearchDataUseCase
from infrastructure.exporters import PandasExporter
from infrastructure.query_catalog import QueryCatalogAdapter
from infrastructure.sap.query_executor import SapQueryExecutor


def build_services() -> dict[str, object]:
    settings = get_settings()
    set_correlation_id()
    catalog = QueryCatalogAdapter(settings.query_catalog_path)
    gateway = SapQueryExecutor(settings)
    run_query = RunQueryUseCase(catalog=catalog, gateway=gateway)
    compute_kpis = ComputeKpisUseCase()
    search = SearchDataUseCase()
    pipeline = PipelineUseCase(run_query=run_query, compute_kpis=compute_kpis)
    export = ExportDataUseCase(PandasExporter())
    compute_commercial_kpis = ComputeCommercialKpisUseCase()
    compute_recommendations = ComputeRecommendationsUseCase()
    commercial_intelligence = CommercialIntelligenceUseCase(
        pipeline=pipeline,
        compute_kpis=compute_commercial_kpis,
        compute_recommendations=compute_recommendations,
    )
    return {
        "settings": settings,
        "catalog": catalog,
        "run_query": run_query,
        "compute_kpis": compute_kpis,
        "search": search,
        "pipeline": pipeline,
        "export": export,
        "compute_commercial_kpis": compute_commercial_kpis,
        "compute_recommendations": compute_recommendations,
        "commercial_intelligence": commercial_intelligence,
    }