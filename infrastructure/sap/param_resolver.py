"""SAP Query parameter resolution for [%N] placeholders.

The SAP Queries web interface does NOT show a popup dialog for [%N] parameters
like the SAP B1 desktop client does. Instead, [%N] is sent literally to the
database, which matches nothing.

This module detects [%N] patterns in SQL text and replaces them with actual
values before execution.
"""

from __future__ import annotations

import re
from typing import Mapping

# Matches [%0], [%1], [%AnyName], etc.
_PARAM_PATTERN = re.compile(r"\[%(\d+)\]")


def extract_param_indices(sql: str) -> list[int]:
    """Return sorted list of unique numeric parameter indices found in SQL.

    >>> extract_param_indices("WHERE x = '[%0]' AND y = '[%1]' AND z = '[%0]'")
    [0, 1]
    """
    return sorted({int(m.group(1)) for m in _PARAM_PATTERN.finditer(sql)})


def has_parameters(sql: str) -> bool:
    """Return True if the SQL contains any [%N] parameter placeholders."""
    return bool(_PARAM_PATTERN.search(sql))


def resolve_parameters(
    sql: str,
    values: Mapping[int, str],
    default: str = "",
) -> tuple[str, dict[int, str]]:
    """Replace [%N] placeholders in SQL with actual values.

    Args:
        sql: The SQL text containing [%N] placeholders.
        values: Mapping of parameter index -> replacement value.
        default: Default value for any parameter not in the mapping.

    Returns:
        Tuple of (resolved_sql, dict of index -> value that was used).

    Example:
        >>> resolve_parameters("WHERE x = '[%0]'", {0: "TEST123"})
        ("WHERE x = 'TEST123'", {0: "TEST123"})
    """
    used: dict[int, str] = {}

    def _replacer(m: re.Match) -> str:
        idx = int(m.group(1))
        value = values.get(idx, default)
        used[idx] = value
        return value

    resolved = _PARAM_PATTERN.sub(_replacer, sql)
    return resolved, used
