import sqlite3
import tempfile
import unittest
from pathlib import Path


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class OpsAlertsMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "ops_alerts.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp_dir.cleanup()

    def apply_migration(self) -> None:
        self.conn.executescript(MIGRATION_PATH.read_text())

    def test_migration_applies_successfully(self) -> None:
        self.apply_migration()

        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ops_alerts'"
        ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "ops_alerts")

    def test_successful_insert_and_query(self) -> None:
        self.apply_migration()

        self.conn.execute(
            """
            INSERT INTO ops_alerts (
                ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                alert_type, status, details_json, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "alert_1",
                "tenant_alpha",
                "act_1",
                "evt_1",
                "booking_failure",
                "open",
                '{"priority":"high"}',
                None,
            ),
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT tenant_id, alert_type, status FROM ops_alerts WHERE ops_alert_id = ?",
            ("alert_1",),
        ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["tenant_id"], "tenant_alpha")
        self.assertEqual(row["alert_type"], "booking_failure")
        self.assertEqual(row["status"], "open")

    def test_required_field_validation(self) -> None:
        self.apply_migration()

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO ops_alerts (
                    ops_alert_id, source_event_id, alert_type, status
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "alert_2",
                    "evt_2",
                    "workflow_failure",
                    "open",
                ),
            )

    def test_tenant_isolation_query(self) -> None:
        self.apply_migration()

        alerts = [
            (
                "alert_3",
                "tenant_alpha",
                "act_3",
                "evt_3",
                "missed_follow_up",
                "open",
                '{"owner":"ops_a"}',
            ),
            (
                "alert_4",
                "tenant_beta",
                "act_4",
                "evt_4",
                "workflow_failure",
                "open",
                '{"owner":"ops_b"}',
            ),
        ]

        self.conn.executemany(
            """
            INSERT INTO ops_alerts (
                ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                alert_type, status, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            alerts,
        )
        self.conn.commit()

        tenant_alpha_rows = self.conn.execute(
            "SELECT ops_alert_id FROM ops_alerts WHERE tenant_id = ? ORDER BY ops_alert_id",
            ("tenant_alpha",),
        ).fetchall()

        self.assertEqual(len(tenant_alpha_rows), 1)
        self.assertEqual(tenant_alpha_rows[0]["ops_alert_id"], "alert_3")


if __name__ == "__main__":
    unittest.main()
