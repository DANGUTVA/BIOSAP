"""YAML-based query catalog adapter."""

from pathlib import Path
import yaml


class QueryCatalogAdapter:
    """Loads query metadata and SQL text from filesystem."""

    def __init__(self, catalog_path: str) -> None:
        self._catalog_path = Path(catalog_path)
        self._catalog = yaml.safe_load(self._catalog_path.read_text(encoding="utf-8"))

    def list_queries(self) -> list[dict]:
        return self._catalog.get("queries", [])

    def get_query_sql(self, query_id: str) -> tuple[dict, str]:
        for item in self.list_queries():
            if item["id"] == query_id:
                sql_path = Path(item["sql_path"])
                return item, sql_path.read_text(encoding="utf-8")
        raise KeyError(f"Query not found: {query_id}")
