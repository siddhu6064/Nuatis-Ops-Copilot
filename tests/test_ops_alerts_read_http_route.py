import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class OpsAlertsReadHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
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

    def test_list_alerts_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_1",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_2",
                "tenant_id": "tenant_b",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        status, response = self.call_get("/internal/alerts", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["tenant_id"], "tenant_a")
        self.assertEqual(len(response["data"]["alerts"]), 1)
        self.assertEqual(response["data"]["alerts"][0]["ops_alert_id"], "alert_1")

    def test_get_alert_by_id_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_3",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )

        status, response = self.call_get("/internal/alerts/alert_3", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["ops_alert_id"], "alert_3")
        self.assertEqual(response["data"]["tenant_id"], "tenant_a")

    def test_missing_tenant_id_returns_400(self) -> None:
        status, response = self.call_get("/internal/alerts")

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_wrong_tenant_or_missing_alert_returns_404(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_4",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )

        wrong_tenant_status, wrong_tenant_response = self.call_get(
            "/internal/alerts/alert_4", "tenant_id=tenant_b"
        )
        missing_status, missing_response = self.call_get(
            "/internal/alerts/not_here", "tenant_id=tenant_a"
        )

        self.assertTrue(wrong_tenant_status.startswith("404"))
        self.assertFalse(wrong_tenant_response["success"])
        self.assertEqual(wrong_tenant_response["error"]["code"], "not_found")

        self.assertTrue(missing_status.startswith("404"))
        self.assertFalse(missing_response["success"])
        self.assertEqual(missing_response["error"]["code"], "not_found")

    def test_tenant_isolation_is_preserved_end_to_end(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_5",
                "tenant_id": "tenant_alpha",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_6",
                "tenant_id": "tenant_beta",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        alpha_list_status, alpha_list_response = self.call_get(
            "/internal/alerts", "tenant_id=tenant_alpha"
        )
        beta_get_status, beta_get_response = self.call_get(
            "/internal/alerts/alert_6", "tenant_id=tenant_beta"
        )
        cross_get_status, cross_get_response = self.call_get(
            "/internal/alerts/alert_6", "tenant_id=tenant_alpha"
        )

        self.assertTrue(alpha_list_status.startswith("200"))
        self.assertEqual(len(alpha_list_response["data"]["alerts"]), 1)
        self.assertEqual(alpha_list_response["data"]["alerts"][0]["ops_alert_id"], "alert_5")

        self.assertTrue(beta_get_status.startswith("200"))
        self.assertEqual(beta_get_response["data"]["tenant_id"], "tenant_beta")

        self.assertTrue(cross_get_status.startswith("404"))
        self.assertFalse(cross_get_response["success"])


if __name__ == "__main__":
    unittest.main()
