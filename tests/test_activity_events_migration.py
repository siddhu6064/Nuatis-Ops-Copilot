import sqlite3
import tempfile
import unittest
from pathlib import Path


MIGRATION_PATH = Path("db/migrations/0001_create_activity_events.sql")


class ActivityEventsMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "ops.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp_dir.cleanup()

    def apply_migration(self) -> None:
        migration_sql = MIGRATION_PATH.read_text()
        self.conn.executescript(migration_sql)

    def test_migration_applies_successfully(self) -> None:
        self.apply_migration()

        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_events'"
        ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "activity_events")

    def test_successful_insert_and_query(self) -> None:
        self.apply_migration()

        self.conn.execute(
            """
            INSERT INTO activity_events (
                activity_event_id, tenant_id, event_id, event_type, event_source,
                occurred_at, payload_json, contact_id, correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt_row_1",
                "tenant_alpha",
                "event_1",
                "call.completed",
                "voice_service",
                "2026-03-25T16:00:00Z",
                '{"duration_seconds": 180}',
                "contact_123",
                "corr_abc",
            ),
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT tenant_id, event_type, event_source FROM activity_events WHERE activity_event_id = ?",
            ("evt_row_1",),
        ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["tenant_id"], "tenant_alpha")
        self.assertEqual(row["event_type"], "call.completed")
        self.assertEqual(row["event_source"], "voice_service")

    def test_required_field_validation(self) -> None:
        self.apply_migration()

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO activity_events (
                    activity_event_id, event_id, event_type, event_source,
                    occurred_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt_row_2",
                    "event_2",
                    "booking.failed",
                    "scheduling_service",
                    "2026-03-25T17:00:00Z",
                    '{"reason": "provider_unavailable"}',
                ),
            )

    def test_tenant_isolation_query(self) -> None:
        self.apply_migration()

        events = [
            (
                "evt_row_3",
                "tenant_alpha",
                "event_3",
                "workflow.failed",
                "worker",
                "2026-03-25T18:00:00Z",
                '{"workflow_id": "wf_1"}',
            ),
            (
                "evt_row_4",
                "tenant_beta",
                "event_4",
                "workflow.failed",
                "worker",
                "2026-03-25T18:05:00Z",
                '{"workflow_id": "wf_2"}',
            ),
        ]

        self.conn.executemany(
            """
            INSERT INTO activity_events (
                activity_event_id, tenant_id, event_id, event_type, event_source,
                occurred_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            events,
        )
        self.conn.commit()

        tenant_alpha_rows = self.conn.execute(
            "SELECT event_id FROM activity_events WHERE tenant_id = ? ORDER BY event_id",
            ("tenant_alpha",),
        ).fetchall()

        self.assertEqual(len(tenant_alpha_rows), 1)
        self.assertEqual(tenant_alpha_rows[0]["event_id"], "event_3")


if __name__ == "__main__":
    unittest.main()
