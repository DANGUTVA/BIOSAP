"""Domain models related to query execution."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QueryDefinition:
    """Catalog definition for a SAP query."""

    query_id: str
    name: str
    description: str
    sql_path: Path
    tags: list[str]
