"""Per-request observability middleware.

For every HTTP request this middleware:

- starts an OpenTelemetry SERVER span (continuing the incoming W3C
  Trace Context if the "traceparent" header is present)
- generates (or forwards) a request id, binds it to the logging
  context, and returns it in the "X-Request-Id" response header
- times database queries and records them in hc_db_queries_duration_seconds
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from django.db import connection
from django.http import HttpRequest, HttpResponse

from hc.lib import observability
from hc.lib.metrics import DB_QUERIES_DURATION
from hc.lib.tracing import extract_context, init_tracing, start_span


def _time_query(
    execute: Callable[..., Any], sql: str, params: Any, many: bool, context: Any
) -> Any:
    start = time.perf_counter()
    try:
        return execute(sql, params, many, context)
    finally:
        DB_QUERIES_DURATION.observe(time.perf_counter() - start)


class ObservabilityMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        init_tracing()
        observability.configure_logging()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-Id") or uuid4().hex
        observability.bind_request_id(request_id)

        attributes = {
            "http.request.method": request.method,
            "url.path": request.path,
            "http.request_id": request_id,
        }
        context = extract_context(request.headers)
        try:
            with start_span(
                f"{request.method} {request.path}",
                attributes=attributes,
                kind="server",
                context=context,
            ) as span:
                with connection.execute_wrapper(_time_query):
                    response = self.get_response(request)

                if span is not None:
                    span.set_attribute(
                        "http.response.status_code", response.status_code
                    )

                response["X-Request-Id"] = request_id
                return response
        finally:
            observability.clear_context()
