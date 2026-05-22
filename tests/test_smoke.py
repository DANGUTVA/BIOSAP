import asyncio
from app.config.settings import Settings
from application.use_cases.compute_kpis import ComputeKpisUseCase
from application.use_cases.search_data import SearchDataUseCase
from infrastructure.query_catalog import QueryCatalogAdapter
from infrastructure.sap.query_executor import SapQueryExecutor


def test_settings_defaults() -> None:
    s = Settings()
    assert s.sap_timeout_seconds > 0


def test_mock_query_execution() -> None:
    settings = Settings(sap_mock_mode=True, mock_fixtures_path="fixtures")
    executor = SapQueryExecutor(settings)
    df = asyncio.run(executor.run_query("sales_by_customer", "SELECT 1", "test-cid"))
    assert not df.empty


def test_kpi_and_search_use_cases() -> None:
    settings = Settings(sap_mock_mode=True, mock_fixtures_path="fixtures")
    executor = SapQueryExecutor(settings)
    df = asyncio.run(executor.run_query("inventory_snapshot", "SELECT 1", "test-cid"))

    kpis = ComputeKpisUseCase().execute(df)
    assert kpis.total_rows == len(df)

    filtered = SearchDataUseCase().execute(df, "I1000")
    assert len(filtered) == 1


def test_query_catalog_loading() -> None:
    catalog = QueryCatalogAdapter("queries/query_catalog.yml")
    queries = catalog.list_queries()
    assert len(queries) >= 2
