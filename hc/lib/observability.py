"""Structured logging via structlog, with a stdlib logging fallback.

Every log entry emitted through loggers returned by get_logger()
automatically includes request_id, check_id, trace_id and span_id
fields (when they are known in the current context).

If structlog is not installed, get_logger() falls back to the standard
logging module.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_check_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "check_id", default=None
)

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

_configured = False


def bind_request_id(value: str | None) -> None:
    _request_id.set(value)


def bind_check_id(value: str | None) -> None:
    _check_id.set(value)


def clear_context() -> None:
    _request_id.set(None)
    _check_id.set(None)


def _inject_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """A structlog processor adding request/check/trace context fields."""

    from hc.lib.tracing import current_trace_ids

    if request_id := _request_id.get():
        event_dict["request_id"] = request_id
    if check_id := _check_id.get():
        event_dict["check_id"] = check_id

    trace_id, span_id = current_trace_ids()
    if trace_id:
        event_dict["trace_id"] = trace_id
    if span_id:
        event_dict["span_id"] = span_id

    return event_dict


def configure_logging() -> None:
    """Configure structlog to render JSON entries through stdlib logging.

    Log records keep their original logger names, so the existing
    LOGGING configuration (including the hc.logs database handler)
    keeps working. Safe to call multiple times.
    """

    global _configured
    if _configured or not STRUCTLOG_AVAILABLE:
        return

    structlog.configure(
        processors=[
            _inject_context,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> Any:
    """Return a structured logger, or a stdlib logger as a fallback."""

    if STRUCTLOG_AVAILABLE:
        configure_logging()
        return structlog.get_logger(name)

    return logging.getLogger(name)
