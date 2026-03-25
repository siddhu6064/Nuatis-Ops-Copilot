import unittest
from pathlib import Path

from api.activity_events_endpoint import ENDPOINT_PATH, ingest_activity_event
from db.connection import connect, disconnect
from repositories.activity_events_repository import ActivityEventsRepository


MIGRATION_PATH = Path("db/migrations/0001_create_activity_events.sql")


class ActivityEventsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = ActivityEventsRepository(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_successful_ingest(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_1",
                "tenant_id": "tenant_1",
                "event_id": "evt_1",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:00:00Z",
                "payload_json": '{"duration": 90}',
            },
            self.db,
        )

        self.assertEqual(status, 201)
        self.assertTrue(response["success"])

        stored = self.repo.get_event_by_id("tenant_1", "ing_1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["event_id"], "evt_1")

    def test_missing_required_field_returns_validation_error(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_2",
                "event_id": "evt_2",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:05:00Z",
                "payload_json": "{}",
            },
            self.db,
        )

        self.assertEqual(status, 400)
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_duplicate_event_returns_conflict(self) -> None:
        payload = {
            "activity_event_id": "ing_3",
            "tenant_id": "tenant_1",
            "event_id": "evt_dup",
            "event_type": "booking.failed",
            "event_source": "scheduler",
            "occurred_at": "2026-03-25T20:10:00Z",
            "payload_json": "{}",
        }

        first_status, _ = ingest_activity_event(payload, self.db)
        second_status, second_response = ingest_activity_event(
            {**payload, "activity_event_id": "ing_4"},
            self.db,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 409)
        self.assertFalse(second_response["success"])
        self.assertEqual(second_response["error"]["code"], "duplicate_event")

    def test_tenant_scoped_ingest_path(self) -> None:
        self.assertEqual(ENDPOINT_PATH, "/internal/events/activity")

        ingest_activity_event(
            {
                "activity_event_id": "ing_5",
                "tenant_id": "tenant_alpha",
                "event_id": "evt_alpha",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T20:20:00Z",
                "payload_json": "{}",
            },
            self.db,
        )
        ingest_activity_event(
            {
                "activity_event_id": "ing_6",
                "tenant_id": "tenant_beta",
                "event_id": "evt_beta",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T20:21:00Z",
                "payload_json": "{}",
            },
            self.db,
        )

        tenant_alpha_events = self.repo.list_events_by_tenant("tenant_alpha")
        self.assertEqual(len(tenant_alpha_events), 1)
        self.assertEqual(tenant_alpha_events[0]["event_id"], "evt_alpha")


if __name__ == "__main__":
    unittest.main()
