from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

from hc.test import BaseTestCase


class HealthTestCase(BaseTestCase):
    url = "/health/"

    def test_it_returns_ok(self) -> None:
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["checks"]["database"]["status"], "ok")
        # S3, SMTP and Redis are not configured in tests:
        self.assertEqual(doc["checks"]["s3"]["status"], "not_configured")
        self.assertEqual(doc["checks"]["smtp"]["status"], "not_configured")
        self.assertEqual(doc["checks"]["redis"]["status"], "not_configured")

    def test_it_handles_db_error(self) -> None:
        cm = MagicMock()
        cm.__enter__.side_effect = Exception("db is down")
        with patch("django.db.connection.cursor", return_value=cm):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 503)
        doc = r.json()
        self.assertEqual(doc["status"], "error")
        self.assertEqual(doc["checks"]["database"]["status"], "error")

    @override_settings(S3_BUCKET="dummy-bucket")
    def test_it_checks_s3(self) -> None:
        with patch("hc.lib.s3.client") as mock_client:
            mock_client.return_value.bucket_exists.return_value = True
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc["checks"]["s3"]["status"], "ok")

    @override_settings(S3_BUCKET="dummy-bucket")
    def test_it_handles_s3_error(self) -> None:
        with patch("hc.lib.s3.client") as mock_client:
            mock_client.side_effect = Exception("s3 is down")
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 503)
        doc = r.json()
        self.assertEqual(doc["checks"]["s3"]["status"], "error")

    @override_settings(EMAIL_HOST="smtp.example.org", EMAIL_PORT=587)
    def test_it_checks_smtp(self) -> None:
        mock_smtp = MagicMock()
        mock_smtp.__enter__.return_value = mock_smtp
        with patch("smtplib.SMTP", return_value=mock_smtp):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc["checks"]["smtp"]["status"], "ok")
        mock_smtp.ehlo.assert_called_once()

    @override_settings(EMAIL_HOST="smtp.example.org", EMAIL_PORT=587)
    def test_it_handles_smtp_error(self) -> None:
        with patch("smtplib.SMTP", side_effect=OSError("smtp is down")):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 503)
        doc = r.json()
        self.assertEqual(doc["checks"]["smtp"]["status"], "error")

    @override_settings(REDIS_URL="redis://localhost:6379/0")
    def test_it_checks_redis(self) -> None:
        try:
            import redis  # noqa: F401
        except ImportError:
            self.skipTest("redis package is not installed")

        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value.ping.return_value = True
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc["checks"]["redis"]["status"], "ok")

    @override_settings(REDIS_URL="redis://localhost:6379/0")
    def test_it_handles_redis_error(self) -> None:
        try:
            import redis  # noqa: F401
        except ImportError:
            self.skipTest("redis package is not installed")

        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value.ping.side_effect = Exception("redis is down")
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 503)
        doc = r.json()
        self.assertEqual(doc["checks"]["redis"]["status"], "error")
