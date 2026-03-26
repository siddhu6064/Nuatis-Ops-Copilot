import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class OpsAlertsDetailHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def call_get(self, path: str, query_string: str = "") -> tuple[str, dict]:
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": "0",
            "wsgi.input": BytesIO(b""),
        }

        captured = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        chunks = self.app(environ, start_response)
        response = json.loads(b"".join(chunks).decode("utf-8"))
        return captured["status"], response

    def test_existing_alert_can_be_fetched_successfully(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "detail_1",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure_high_severity",
                "status": "open",
                "details_json": '{"detector_name":"booking_failure_high_severity"}',
            }
        )

        status, response = self.call_get("/internal/alerts/detail_1/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["ops_alert_id"], "detail_1")
        self.assertEqual(response["data"]["status"], "open")
        self.assertIn("created_at", response["data"])
        self.assertIn("details_json", response["data"])

    def test_tenant_isolation_prevents_reading_another_tenants_alert(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "detail_2",
                "tenant_id": "tenant_alpha",
                "alert_type": "booking_failure_high_severity",
                "status": "open",
            }
        )

        status, response = self.call_get("/internal/alerts/detail_2/detail", "tenant_id=tenant_beta")

        self.assertTrue(status.startswith("404"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "not_found")

    def test_non_existent_alert_returns_404(self) -> None:
        status, response = self.call_get("/internal/alerts/not_here/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("404"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "not_found")

    def test_resolved_alert_returns_resolved_metadata(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "detail_3",
                "tenant_id": "tenant_a",
                "alert_type": "call_failure_high_severity",
                "status": "resolved",
                "resolved_at": "2026-03-26T12:00:00Z",
                "resolved_by": "ops_user_7",
            }
        )

        status, response = self.call_get("/internal/alerts/detail_3/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["data"]["status"], "resolved")
        self.assertEqual(response["data"]["resolved_at"], "2026-03-26T12:00:00Z")
        self.assertEqual(response["data"]["resolved_by"], "ops_user_7")

    def test_detector_attribution_is_visible_in_details_json(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "detail_4",
                "tenant_id": "tenant_a",
                "alert_type": "call_failure_high_severity",
                "status": "open",
                "details_json": json.dumps(
                    {
                        "payload": {"rule": "call.failed + severity=high"},
                        "severity": "high",
                        "detector_name": "call_failure_high_severity",
                        "metadata": {"source_event_id": "evt_200"},
                    }
                ),
            }
        )

        status, response = self.call_get("/internal/alerts/detail_4/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        details = json.loads(response["data"]["details_json"])
        self.assertEqual(details["detector_name"], "call_failure_high_severity")


if __name__ == "__main__":
    unittest.main()
