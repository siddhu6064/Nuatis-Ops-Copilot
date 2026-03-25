import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class OpsAlertsResolveHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def call_post(self, path: str, query_string: str = "", payload: dict | None = None) -> tuple[str, dict]:
        body = json.dumps(payload or {}).encode("utf-8")
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": BytesIO(body),
        }

        captured = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        chunks = self.app(environ, start_response)
        response = json.loads(b"".join(chunks).decode("utf-8"))
        return captured["status"], response

    def test_resolve_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "resolve_1",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        status, response = self.call_post(
            "/internal/alerts/resolve_1/resolve",
            "tenant_id=tenant_a",
            {"resolved_at": "2026-03-26T00:00:00Z"},
        )

        self.assertTrue(status.startswith("200"))
        self.assertTrue(response["success"])

        alert = self.repo.get_alert_by_id("tenant_a", "resolve_1")
        self.assertEqual(alert["status"], "resolved")
        self.assertEqual(alert["resolved_at"], "2026-03-26T00:00:00Z")

    def test_resolve_wrong_tenant_or_missing_alert(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "resolve_2",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        wrong_tenant_status, _ = self.call_post(
            "/internal/alerts/resolve_2/resolve", "tenant_id=tenant_b"
        )
        missing_status, _ = self.call_post(
            "/internal/alerts/not_here/resolve", "tenant_id=tenant_a"
        )

        self.assertTrue(wrong_tenant_status.startswith("404"))
        self.assertTrue(missing_status.startswith("404"))

    def test_missing_tenant_id_returns_400(self) -> None:
        status, response = self.call_post("/internal/alerts/resolve_3/resolve")

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_invalid_resolved_at_returns_400(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "resolve_4",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        status, response = self.call_post(
            "/internal/alerts/resolve_4/resolve",
            "tenant_id=tenant_a",
            {"resolved_at": "bad-time"},
        )

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_resolve_with_resolved_by_and_repeat_preserves_original_metadata(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "resolve_5",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        first_status, _ = self.call_post(
            "/internal/alerts/resolve_5/resolve",
            "tenant_id=tenant_a",
            {"resolved_at": "2026-03-26T01:00:00Z", "resolved_by": "ops_user_1"},
        )
        second_status, _ = self.call_post(
            "/internal/alerts/resolve_5/resolve",
            "tenant_id=tenant_a",
            {"resolved_at": "2026-03-26T01:05:00Z", "resolved_by": "ops_user_2"},
        )

        self.assertTrue(first_status.startswith("200"))
        self.assertTrue(second_status.startswith("200"))

        alert = self.repo.get_alert_by_id("tenant_a", "resolve_5")
        self.assertEqual(alert["resolved_at"], "2026-03-26T01:00:00Z")
        self.assertEqual(alert["resolved_by"], "ops_user_1")


