from __future__ import annotations

from unittest import skipUnless

from hc.api.models import Check
from hc.lib import metrics
from hc.lib.metrics import PROM_AVAILABLE
from hc.test import BaseTestCase


@skipUnless(PROM_AVAILABLE, "prometheus-client is not installed")
class PrometheusMetricsTestCase(BaseTestCase):
    url = "/metrics"

    def test_it_serves_metrics(self) -> None:
        # Labelled series only appear in the exposition format after
        # they have been observed at least once:
        metrics.PINGS_TOTAL.labels(action="success").inc()
        metrics.ALERTS_SENT.labels(kind="email").inc()
        metrics.ALERTS_ERRORS.labels(kind="email").inc()
        metrics.S3_OPERATIONS.labels(operation="getObject", status="ok").inc()
        metrics.DB_QUERIES_DURATION.observe(0.001)

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r["Content-Type"])

        body = r.content.decode()
        self.assertIn("hc_pings_total", body)
        self.assertIn("hc_alerts_sent_total", body)
        self.assertIn("hc_alerts_errors_total", body)
        self.assertIn("hc_s3_operations_total", body)
        self.assertIn("hc_db_queries_duration_seconds", body)

    def test_it_counts_pings(self) -> None:
        check = Check.objects.create(project=self.project)
        r = self.client.get(f"/ping/{check.code}")
        self.assertEqual(r.status_code, 200)

        r = self.client.get(self.url)
        body = r.content.decode()
        self.assertIn('hc_pings_total{action="success"}', body)

    def test_it_records_db_query_durations(self) -> None:
        # A ping request goes through ObservabilityMiddleware, which times
        # the request's database queries:
        check = Check.objects.create(project=self.project)
        r = self.client.get(f"/ping/{check.code}")
        self.assertEqual(r.status_code, 200)

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("hc_db_queries_duration_seconds_count", r.content.decode())
