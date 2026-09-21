from __future__ import annotations

from unittest import skipUnless

from django.test import SimpleTestCase

from hc.lib import metrics, observability, tracing


class MetricsTestCase(SimpleTestCase):
    def test_metrics_accept_calls(self) -> None:
        # Works both with real prometheus-client and with no-op doubles
        metrics.PINGS_TOTAL.labels(action="success").inc()
        metrics.PINGS_DURATION.labels(action="success").observe(0.01)
        metrics.ALERTS_SENT.labels(kind="email").inc()
        metrics.ALERTS_ERRORS.labels(kind="email").inc()
        metrics.ALERTS_SEND_DURATION.labels(kind="email").observe(0.5)
        metrics.S3_OPERATIONS.labels(operation="getObject", status="ok").inc()
        metrics.S3_OPERATION_DURATION.labels(operation="getObject").observe(0.1)
        metrics.DB_QUERIES_DURATION.observe(0.001)

    @skipUnless(metrics.PROM_AVAILABLE, "prometheus-client is not installed")
    def test_render_metrics(self) -> None:
        metrics.PINGS_TOTAL.labels(action="success").inc()
        content, content_type = metrics.render_metrics()
        self.assertIn(b"hc_pings_total", content)
        self.assertIn(b"hc_pings_duration_seconds", content)
        self.assertIn(b"hc_alerts_sent_total", content)
        self.assertIn(b"hc_alerts_errors_total", content)
        self.assertIn(b"hc_s3_operations_total", content)
        self.assertIn(b"hc_db_queries_duration_seconds", content)
        self.assertIn("text/plain", content_type)

    def test_render_metrics_raises_without_client(self) -> None:
        if metrics.PROM_AVAILABLE:
            self.skipTest("prometheus-client is installed")
        with self.assertRaises(RuntimeError):
            metrics.render_metrics()


class TracingTestCase(SimpleTestCase):
    def test_init_tracing_is_safe_to_call(self) -> None:
        # OTEL_ENABLED defaults to False, so this must be a no-op
        tracing.init_tracing()
        tracing.init_tracing()

    def test_start_span_yields(self) -> None:
        with tracing.start_span("test.span", attributes={"k": "v"}) as span:
            if not tracing.OTEL_AVAILABLE:
                self.assertIsNone(span)

    def test_extract_and_inject_do_not_raise(self) -> None:
        carrier: dict[str, str] = {}
        tracing.inject_trace_context(carrier)
        tracing.extract_context(carrier)

    def test_current_trace_ids(self) -> None:
        trace_id, span_id = tracing.current_trace_ids()
        if not tracing.OTEL_AVAILABLE:
            self.assertIsNone(trace_id)
            self.assertIsNone(span_id)


class ObservabilityTestCase(SimpleTestCase):
    def test_get_logger_logs_without_raising(self) -> None:
        logger = observability.get_logger("hc.test")
        logger.info("test event")
        if observability.STRUCTLOG_AVAILABLE:
            logger.info("test event", extra_field="extra_value")

    def test_bind_and_clear_context(self) -> None:
        observability.bind_request_id("req-123")
        observability.bind_check_id("check-456")
        observability.clear_context()

    def test_inject_context_adds_fields(self) -> None:
        observability.bind_request_id("req-123")
        observability.bind_check_id("check-456")
        try:
            event_dict = observability._inject_context(None, "info", {})  # type: ignore[arg-type]
            self.assertEqual(event_dict["request_id"], "req-123")
            self.assertEqual(event_dict["check_id"], "check-456")
        finally:
            observability.clear_context()

        event_dict = observability._inject_context(None, "info", {})  # type: ignore[arg-type]
        self.assertNotIn("request_id", event_dict)
        self.assertNotIn("check_id", event_dict)
