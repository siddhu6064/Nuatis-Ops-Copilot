import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class OpsAlertsReadHttpRouteTests(unittest.TestCase):
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

    def test_list_alerts_filters_and_pagination(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_7",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_8",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "resolved",
            }
        )

        status, response = self.call_get(
            "/internal/alerts",
            "tenant_id=tenant_a&status=open&limit=1&offset=0",
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(len(response["data"]["alerts"]), 1)
        self.assertEqual(response["data"]["alerts"][0]["ops_alert_id"], "alert_7")
        self.assertEqual(response["data"]["pagination"]["limit"], 1)
        self.assertEqual(response["data"]["pagination"]["offset"], 0)

    def test_invalid_query_params_return_400(self) -> None:
        status, response = self.call_get("/internal/alerts", "tenant_id=tenant_a&limit=bad")

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_invalid_status_filter_returns_400(self) -> None:
        status, response = self.call_get("/internal/alerts", "tenant_id=tenant_a&status=closed")

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_invalid_sort_order_returns_400(self) -> None:
        status, response = self.call_get("/internal/alerts", "tenant_id=tenant_a&sort_order=newest")

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_limit_is_capped_to_200(self) -> None:
        status, response = self.call_get("/internal/alerts", "tenant_id=tenant_a&limit=999")

        self.assertTrue(status.startswith("200"))
        self.assertEqual(response["data"]["pagination"]["limit"], 200)

    def test_status_filter_open_and_resolved_return_expected_rows(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_9",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_10",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "resolved",
            }
        )

        open_status, open_response = self.call_get("/internal/alerts", "tenant_id=tenant_a&status=open")
        resolved_status, resolved_response = self.call_get(
            "/internal/alerts", "tenant_id=tenant_a&status=resolved"
        )

        self.assertTrue(open_status.startswith("200"))
        self.assertEqual(len(open_response["data"]["alerts"]), 1)
        self.assertEqual(open_response["data"]["alerts"][0]["ops_alert_id"], "alert_9")

        self.assertTrue(resolved_status.startswith("200"))
        self.assertEqual(len(resolved_response["data"]["alerts"]), 1)
        self.assertEqual(resolved_response["data"]["alerts"][0]["ops_alert_id"], "alert_10")


    def test_invalid_created_after_returns_400(self) -> None:
        status, response = self.call_get(
            "/internal/alerts", "tenant_id=tenant_a&created_after=bad-time"
        )

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_deterministic_ordering_uses_ops_alert_id_tie_breaker(self) -> None:
        self.db.connection.execute(
            """
            INSERT INTO ops_alerts (
                ops_alert_id, tenant_id, alert_type, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("alert_a", "tenant_a", "workflow_failure", "open", "2026-03-26T10:00:00Z"),
        )
        self.db.connection.execute(
            """
            INSERT INTO ops_alerts (
                ops_alert_id, tenant_id, alert_type, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("alert_b", "tenant_a", "workflow_failure", "open", "2026-03-26T10:00:00Z"),
        )
        self.db.connection.commit()

        desc_status, desc_response = self.call_get(
            "/internal/alerts", "tenant_id=tenant_a&sort_order=desc"
        )
        asc_status, asc_response = self.call_get("/internal/alerts", "tenant_id=tenant_a&sort_order=asc")

        self.assertTrue(desc_status.startswith("200"))
        self.assertEqual(desc_response["data"]["alerts"][0]["ops_alert_id"], "alert_b")
        self.assertEqual(desc_response["data"]["alerts"][1]["ops_alert_id"], "alert_a")

        self.assertTrue(asc_status.startswith("200"))
        self.assertEqual(asc_response["data"]["alerts"][0]["ops_alert_id"], "alert_a")
        self.assertEqual(asc_response["data"]["alerts"][1]["ops_alert_id"], "alert_b")


    def test_read_path_returns_resolved_by_metadata_when_present(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_11",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "resolved",
                "resolved_at": "2026-03-26T01:10:00Z",
                "resolved_by": "ops_user_1",
            }
        )

        list_status, list_response = self.call_get("/internal/alerts", "tenant_id=tenant_a&status=resolved")
        get_status, get_response = self.call_get("/internal/alerts/alert_11", "tenant_id=tenant_a")

        self.assertTrue(list_status.startswith("200"))
        self.assertEqual(list_response["data"]["alerts"][0]["resolved_by"], "ops_user_1")

        self.assertTrue(get_status.startswith("200"))
        self.assertEqual(get_response["data"]["resolved_by"], "ops_user_1")



if __name__ == "__main__":
    unittest.main()
