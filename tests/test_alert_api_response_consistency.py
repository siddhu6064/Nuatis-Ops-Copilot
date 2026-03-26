import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository

MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class AlertApiResponseConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def call(self, method: str, path: str, query: str = "", payload: dict | None = None) -> tuple[str, dict]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": BytesIO(body),
        }
        captured = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        chunks = self.app(environ, start_response)
        return captured["status"], json.loads(b"".join(chunks).decode("utf-8"))

    def test_list_success_response_shape(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "shape_1",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )
        status, response = self.call("GET", "/internal/alerts", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertEqual(set(response.keys()), {"success", "data", "meta"})
        self.assertTrue(response["success"])
        self.assertIsInstance(response["data"], list)
        self.assertIn("pagination", response["meta"])

    def test_detail_success_response_shape(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "shape_2",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )
        status, response = self.call("GET", "/internal/alerts/shape_2/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("200"))
        self.assertEqual(set(response.keys()), {"success", "data"})
        self.assertTrue(response["success"])

    def test_bulk_resolve_success_response_shape(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "shape_3",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )
        status, response = self.call(
            "POST",
            "/internal/alerts/resolve/bulk",
            payload={"tenant_id": "tenant_a", "ops_alert_ids": ["shape_3"], "resolved_by": "ops_user"},
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(set(response.keys()), {"success", "data", "meta"})
        self.assertTrue(response["success"])
        self.assertIsInstance(response["data"], list)
        self.assertIn("resolved_count", response["meta"])

    def test_single_resolve_success_response_shape(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "shape_4",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )
        status, response = self.call(
            "POST",
            "/internal/alerts/shape_4/resolve",
            query="tenant_id=tenant_a",
            payload={"resolved_by": "ops_user"},
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(set(response.keys()), {"success", "data"})
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["ops_alert_id"], "shape_4")

    def test_error_response_shape_for_400(self) -> None:
        status, response = self.call(
            "POST",
            "/internal/alerts/resolve/bulk",
            payload={"tenant_id": "tenant_a", "ops_alert_ids": []},
        )

        self.assertTrue(status.startswith("400"))
        self.assertEqual(set(response.keys()), {"success", "error"})
        self.assertFalse(response["success"])
        self.assertEqual(set(response["error"].keys()), {"code", "message"})

    def test_error_response_shape_for_404(self) -> None:
        status, response = self.call("GET", "/internal/alerts/not_here/detail", "tenant_id=tenant_a")

        self.assertTrue(status.startswith("404"))
        self.assertEqual(set(response.keys()), {"success", "error"})
        self.assertFalse(response["success"])
        self.assertEqual(set(response["error"].keys()), {"code", "message"})

    def test_error_response_shape_for_404_on_single_resolve(self) -> None:
        status, response = self.call(
            "POST",
            "/internal/alerts/not_here/resolve",
            query="tenant_id=tenant_a",
            payload={"resolved_by": "ops_user"},
        )

        self.assertTrue(status.startswith("404"))
        self.assertEqual(set(response.keys()), {"success", "error"})
        self.assertFalse(response["success"])
        self.assertEqual(set(response["error"].keys()), {"code", "message"})
