"""Application settings using environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sap_base_url: str = "https://sap.example.com"
    sap_username: str = ""
    sap_password: str = ""
    sap_company_db: str = ""
    sap_mock_mode: bool = True
    sap_timeout_seconds: int = 30
    sap_headless: bool = True
    sap_debug_capture: bool = True
    sap_debug_artifacts_path: str = "artifacts/live_debug"

    log_level: str = "INFO"
    query_catalog_path: str = "queries/query_catalog.yml"
    mock_fixtures_path: str = "fixtures"
    cache_ttl_seconds: int = 300
    scheduler_enabled: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
