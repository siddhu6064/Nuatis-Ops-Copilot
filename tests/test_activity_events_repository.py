import sqlite3
import unittest
from pathlib import Path

from db.connection import connect, disconnect
from repositories.activity_events_repository import ActivityEventsRepository


MIGRATION_PATH = Path("db/migrations/0001_create_activity_events.sql")


class ActivityEventsRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = ActivityEventsRepository(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_create_event_success(self) -> None:
        self.repo.create_event(
            {
                "activity_event_id": "act_1",
                "tenant_id": "tenant_a",
                "event_id": "evt_1",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T10:00:00Z",
                "payload_json": '{"duration":120}',
            }
        )

        row = self.db.connection.execute(
            "SELECT event_id FROM activity_events WHERE activity_event_id = ?",
            ("act_1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "evt_1")

    def test_get_by_id_success(self) -> None:
        self.repo.create_event(
            {
                "activity_event_id": "act_2",
                "tenant_id": "tenant_a",
                "event_id": "evt_2",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T11:00:00Z",
                "payload_json": '{"reason":"conflict"}',
            }
        )

        event = self.repo.get_event_by_id("tenant_a", "act_2")

        self.assertIsNotNone(event)
        self.assertEqual(event["event_id"], "evt_2")
        self.assertEqual(event["tenant_id"], "tenant_a")

    def test_list_by_tenant_returns_only_that_tenants_rows(self) -> None:
        self.repo.create_event(
            {
                "activity_event_id": "act_3",
                "tenant_id": "tenant_a",
                "event_id": "evt_3",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T12:00:00Z",
                "payload_json": '{}',
            }
        )
        self.repo.create_event(
            {
                "activity_event_id": "act_4",
                "tenant_id": "tenant_b",
                "event_id": "evt_4",
                "event_type": "workflow.failed",
                "event_source": "worker",
                "occurred_at": "2026-03-25T12:05:00Z",
                "payload_json": '{}',
            }
        )

        tenant_a_events = self.repo.list_events_by_tenant("tenant_a")

        self.assertEqual(len(tenant_a_events), 1)
        self.assertEqual(tenant_a_events[0]["tenant_id"], "tenant_a")
        self.assertEqual(tenant_a_events[0]["activity_event_id"], "act_3")

    def test_duplicate_tenant_event_id_raises_integrity_error(self) -> None:
        event = {
            "activity_event_id": "act_5",
            "tenant_id": "tenant_a",
            "event_id": "evt_dup",
            "event_type": "call.completed",
            "event_source": "voice",
            "occurred_at": "2026-03-25T13:00:00Z",
            "payload_json": '{}',
        }
        self.repo.create_event(event)

        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.create_event(
                {
                    **event,
                    "activity_event_id": "act_6",
                }
            )


if __name__ == "__main__":
    unittest.main()
