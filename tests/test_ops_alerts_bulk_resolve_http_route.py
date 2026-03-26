import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class OpsAlertsBulkResolveHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def call_post(self, payload: dict | None) -> tuple[str, dict]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/internal/alerts/resolve/bulk",
            "QUERY_STRING": "",
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

    def seed_alert(self, ops_alert_id: str, tenant_id: str, status: str = "open") -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": ops_alert_id,
                "tenant_id": tenant_id,
                "alert_type": "workflow_failure",
                "status": status,
            }
        )

    def test_multiple_open_alerts_resolved_successfully(self) -> None:
        self.seed_alert("bulk_1", "tenant_a")
        self.seed_alert("bulk_2", "tenant_a")

        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": ["bulk_1", "bulk_2"],
                "resolved_by": "ops_user_1",
                "resolved_at": "2026-03-26T16:00:00Z",
            }
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["meta"]["requested_count"], 2)
        self.assertEqual(response["meta"]["resolved_count"], 2)
        self.assertEqual(response["meta"]["already_resolved_count"], 0)
        self.assertEqual(response["meta"]["not_found_count"], 0)

    def test_duplicate_ids_are_tolerated_safely(self) -> None:
        self.seed_alert("bulk_dup", "tenant_a")

        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": ["bulk_dup", "bulk_dup"],
                "resolved_by": "ops_user_1",
            }
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["meta"]["requested_count"], 2)
        self.assertEqual(response["meta"]["resolved_count"], 1)
        self.assertEqual(response["meta"]["not_found_count"], 0)

    def test_already_resolved_alert_remains_idempotent(self) -> None:
        self.seed_alert("bulk_r1", "tenant_a", status="resolved")

        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": ["bulk_r1"],
                "resolved_by": "ops_user_2",
            }
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["meta"]["resolved_count"], 0)
        self.assertEqual(response["meta"]["already_resolved_count"], 1)

    def test_another_tenants_alert_is_not_affected(self) -> None:
        self.seed_alert("bulk_cross", "tenant_b")

        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": ["bulk_cross"],
                "resolved_by": "ops_user_1",
            }
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["meta"]["not_found_count"], 1)

        tenant_b_alert = self.repo.get_alert_by_id("tenant_b", "bulk_cross")
        self.assertEqual(tenant_b_alert["status"], "open")

    def test_non_existent_alert_id_is_handled_safely(self) -> None:
        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": ["bulk_missing"],
                "resolved_by": "ops_user_1",
            }
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["meta"]["resolved_count"], 0)
        self.assertEqual(response["meta"]["not_found_count"], 1)

    def test_invalid_request_body_returns_400(self) -> None:
        status, response = self.call_post(
            {
                "tenant_id": "tenant_a",
                "ops_alert_ids": [],
                "resolved_by": "ops_user_1",
            }
        )

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
