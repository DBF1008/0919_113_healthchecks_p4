"""OpenTelemetry tracing integration with graceful fallback.

If the opentelemetry packages are not installed, or settings.OTEL_ENABLED
is False, all helpers in this module become no-ops, so the rest of the
codebase can call them unconditionally.

Spans are exported to an OTLP collector over HTTP. Context propagation
uses the W3C Trace Context format (the "traceparent" header).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from django.conf import settings

try:
    from opentelemetry import trace
    from opentelemetry.propagate import extract, inject
    from opentelemetry.trace import SpanKind

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

_initialized = False

_KINDS = {
    "server": "SERVER",
    "client": "CLIENT",
    "internal": "INTERNAL",
    "producer": "PRODUCER",
    "consumer": "CONSUMER",
}


def init_tracing() -> None:
    """Set up the global tracer provider with a batching OTLP exporter.

    Safe to call multiple times: initialization runs at most once.
    """

    global _initialized
    if _initialized or not OTEL_AVAILABLE:
        return
    if not getattr(settings, "OTEL_ENABLED", False):
        return

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True


def _span_kind(kind: str | None) -> Any:
    if not OTEL_AVAILABLE or kind is None:
        return None
    return getattr(SpanKind, _KINDS.get(kind, "INTERNAL"))


@contextmanager
def start_span(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
    kind: str | None = None,
    context: Any = None,
) -> Iterator[Any]:
    """Start a span as the current span, yield it (or None if OTel missing)."""

    if not OTEL_AVAILABLE:
        yield None
        return

    kwargs: dict[str, Any] = {"attributes": dict(attributes or {})}
    span_kind = _span_kind(kind)
    if span_kind is not None:
        kwargs["kind"] = span_kind
    if context is not None:
        kwargs["context"] = context

    tracer = trace.get_tracer("hc")
    with tracer.start_as_current_span(name, **kwargs) as span:
        yield span


def extract_context(carrier: Mapping[str, str]) -> Any:
    """Extract a W3C Trace Context from incoming HTTP headers."""

    if not OTEL_AVAILABLE:
        return None
    return extract(carrier)


def inject_trace_context(carrier: dict[str, str]) -> None:
    """Inject the current span context as W3C "traceparent" header."""

    if OTEL_AVAILABLE:
        inject(carrier)


def current_trace_ids() -> tuple[str | None, str | None]:
    """Return (trace_id, span_id) of the current span as hex strings."""

    if not OTEL_AVAILABLE:
        return None, None

    ctx = trace.get_current_span().get_span_context()
    if ctx is None or not ctx.is_valid:
        return None, None

    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
