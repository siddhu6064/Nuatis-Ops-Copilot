import json
import unittest
from io import BytesIO
from pathlib import Path

from api.http_app import create_app
from db.connection import connect, disconnect
from repositories.activity_events_repository import ActivityEventsRepository


MIGRATION_PATH = Path("db/migrations/0001_create_activity_events.sql")


class ActivityEventsHttpRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = ActivityEventsRepository(self.db)
        self.app = create_app(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def call_post(self, payload: dict) -> tuple[str, dict]:
        body = json.dumps(payload).encode("utf-8")
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/internal/events/activity",
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

    def test_post_success_returns_201(self) -> None:
        status, response = self.call_post(
            {
                "activity_event_id": "http_1",
                "tenant_id": "tenant_a",
                "event_id": "evt_1",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T21:00:00Z",
                "payload_json": "{}",
            }
        )

        self.assertTrue(status.startswith("201"))
        self.assertTrue(response["success"])

    def test_post_missing_required_field_returns_400(self) -> None:
        status, response = self.call_post(
            {
                "activity_event_id": "http_2",
                "event_id": "evt_2",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T21:05:00Z",
                "payload_json": "{}",
            }
        )

        self.assertTrue(status.startswith("400"))
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_post_duplicate_returns_409(self) -> None:
        payload = {
            "activity_event_id": "http_3",
            "tenant_id": "tenant_a",
            "event_id": "evt_dup",
            "event_type": "booking.failed",
            "event_source": "scheduler",
            "occurred_at": "2026-03-25T21:10:00Z",
            "payload_json": "{}",
        }

        first_status, _ = self.call_post(payload)
        second_status, second_response = self.call_post(
            {**payload, "activity_event_id": "http_4"}
        )

        self.assertTrue(first_status.startswith("201"))
        self.assertTrue(second_status.startswith("409"))
        self.assertFalse(second_response["success"])
        self.assertEqual(second_response["error"]["code"], "duplicate_event")

    def test_tenant_scoped_payload_works_through_http_layer(self) -> None:
        self.call_post(
            {
                "activity_event_id": "http_5",
                "tenant_id": "tenant_alpha",
                "event_id": "evt_alpha",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T21:15:00Z",
                "payload_json": "{}",
            }
        )
        self.call_post(
            {
                "activity_event_id": "http_6",
                "tenant_id": "tenant_beta",
                "event_id": "evt_beta",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T21:16:00Z",
                "payload_json": "{}",
            }
        )

        tenant_alpha_events = self.repo.list_events_by_tenant("tenant_alpha")
        self.assertEqual(len(tenant_alpha_events), 1)
        self.assertEqual(tenant_alpha_events[0]["event_id"], "evt_alpha")


if __name__ == "__main__":
    unittest.main()
