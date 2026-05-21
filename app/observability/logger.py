"""Correlation-aware logging setup."""

import contextvars
import logging
import uuid


correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


def set_correlation_id(value: str | None = None) -> str:
    """Set correlation id in context and return it."""
    cid = value or str(uuid.uuid4())
    correlation_id_ctx.set(cid)
    return cid


class CorrelationIdFilter(logging.Filter):
    """Inject correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get() or "n/a"
        return True


def configure_logger(level: str = "INFO") -> logging.Logger:
    """Configure root logger with correlation_id support."""
    logger = logging.getLogger("sap_app")
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [cid=%(correlation_id)s] %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())
        logger.addHandler(handler)
    return logger
