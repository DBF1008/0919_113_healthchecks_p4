"""Prometheus metrics with graceful fallback.

If prometheus-client is not installed, every metric object becomes a
no-op double, so instrumentation call sites do not need to check for
availability.
"""

from __future__ import annotations

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    PROM_AVAILABLE = True
except ImportError:
    PROM_AVAILABLE = False


class _NoopMetric:
    """A stand-in for Counter/Histogram when prometheus-client is missing."""

    def labels(self, *args: object, **kwargs: object) -> _NoopMetric:
        return self

    def inc(self, amount: float = 1.0) -> None:
        pass

    def observe(self, amount: float) -> None:
        pass


if PROM_AVAILABLE:
    PINGS_TOTAL = Counter(
        "hc_pings_total",
        "Total number of received pings.",
        ["action"],
    )
    PINGS_DURATION = Histogram(
        "hc_pings_duration_seconds",
        "Time spent processing a ping request.",
        ["action"],
    )
    ALERTS_SENT = Counter(
        "hc_alerts_sent_total",
        "Total number of successfully sent alert notifications.",
        ["kind"],
    )
    ALERTS_ERRORS = Counter(
        "hc_alerts_errors_total",
        "Total number of failed alert notifications.",
        ["kind"],
    )
    ALERTS_SEND_DURATION = Histogram(
        "hc_alerts_send_duration_seconds",
        "Time spent sending a single alert notification.",
        ["kind"],
    )
    S3_OPERATIONS = Counter(
        "hc_s3_operations_total",
        "Total number of S3 object storage operations.",
        ["operation", "status"],
    )
    S3_OPERATION_DURATION = Histogram(
        "hc_s3_operations_duration_seconds",
        "Time spent on an S3 object storage operation.",
        ["operation"],
    )
    DB_QUERIES_DURATION = Histogram(
        "hc_db_queries_duration_seconds",
        "Time spent executing a database query.",
    )
else:
    PINGS_TOTAL = _NoopMetric()
    PINGS_DURATION = _NoopMetric()
    ALERTS_SENT = _NoopMetric()
    ALERTS_ERRORS = _NoopMetric()
    ALERTS_SEND_DURATION = _NoopMetric()
    S3_OPERATIONS = _NoopMetric()
    S3_OPERATION_DURATION = _NoopMetric()
    DB_QUERIES_DURATION = _NoopMetric()


def render_metrics() -> tuple[bytes, str]:
    """Render all registered metrics in the Prometheus text format.

    Returns a (content, content_type) tuple. Raises RuntimeError if
    prometheus-client is not installed.
    """

    if not PROM_AVAILABLE:
        raise RuntimeError("prometheus-client is not installed")

    return generate_latest(), CONTENT_TYPE_LATEST
