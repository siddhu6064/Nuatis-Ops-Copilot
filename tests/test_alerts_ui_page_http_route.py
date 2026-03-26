import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect


MIGRATION_EVENTS_PATH = Path("db/migrations/0001_create_activity_events.sql")
MIGRATION_ALERTS_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class AlertsUiPageHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_EVENTS_PATH.read_text())
        self.db.connection.executescript(MIGRATION_ALERTS_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_get_ui_alerts_page_returns_html(self) -> None:
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/ui/alerts",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "wsgi.input": BytesIO(b""),
        }
        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        response_bytes = b"".join(self.app(environ, start_response))
        response_text = response_bytes.decode("utf-8")

        self.assertTrue(str(captured["status"]).startswith("200"))
        self.assertIn("Ops Alerts", response_text)
        self.assertIn("new URLSearchParams({ tenant_id: tenantId })", response_text)
        self.assertIn("id=\"status_filter\"", response_text)
        self.assertIn("id=\"refresh_alerts\"", response_text)
        self.assertIn("query.set(\"status\", statusValue)", response_text)
        self.assertIn("/internal/alerts/${encodeURIComponent(opsAlertId)}/detail", response_text)
        self.assertIn("id=\"resolved_by\"", response_text)
        self.assertIn("/resolve?tenant_id=", response_text)


if __name__ == "__main__":
    unittest.main()
