"""Domain-level custom errors."""


class SapAppError(Exception):
    """Base app error."""


class SapConnectionError(SapAppError):
    """Raised when SAP session fails."""


class SapQueryExecutionError(SapAppError):
    """Raised when query execution fails."""


class SapSelectorError(SapAppError):
    """Raised when browser selectors are stale or invalid."""


class ParserError(SapAppError):
    """Raised when HTML parsing fails."""
