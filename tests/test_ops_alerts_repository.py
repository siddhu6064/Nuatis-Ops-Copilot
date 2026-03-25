import unittest
from pathlib import Path

from db.connection import connect, disconnect
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class OpsAlertsRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_create_alert_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_1",
                "tenant_id": "tenant_a",
                "source_activity_event_id": "act_1",
                "source_event_id": "evt_1",
                "alert_type": "booking_failure",
                "status": "open",
                "details_json": '{"priority":"high"}',
            }
        )

        row = self.db.connection.execute(
            "SELECT alert_type FROM ops_alerts WHERE ops_alert_id = ?",
            ("alert_repo_1",),
        ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "booking_failure")

    def test_get_by_id_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_2",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        alert = self.repo.get_alert_by_id("tenant_a", "alert_repo_2")

        self.assertIsNotNone(alert)
        self.assertEqual(alert["ops_alert_id"], "alert_repo_2")
        self.assertEqual(alert["tenant_id"], "tenant_a")

    def test_list_by_tenant_returns_only_that_tenants_rows(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_3",
                "tenant_id": "tenant_a",
                "alert_type": "stale_contact",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_4",
                "tenant_id": "tenant_b",
                "alert_type": "stale_contact",
                "status": "open",
            }
        )

        tenant_a_alerts = self.repo.list_alerts_by_tenant("tenant_a")

        self.assertEqual(len(tenant_a_alerts), 1)
        self.assertEqual(tenant_a_alerts[0]["ops_alert_id"], "alert_repo_3")
        self.assertEqual(tenant_a_alerts[0]["tenant_id"], "tenant_a")

    def test_resolve_alert_success(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_5",
                "tenant_id": "tenant_a",
                "alert_type": "missed_follow_up",
                "status": "open",
            }
        )

        updated = self.repo.resolve_alert("tenant_a", "alert_repo_5", "2026-03-25T22:00:00Z")

        self.assertTrue(updated)

        alert = self.repo.get_alert_by_id("tenant_a", "alert_repo_5")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["status"], "resolved")
        self.assertEqual(alert["resolved_at"], "2026-03-25T22:00:00Z")

    def test_tenant_isolation_on_resolve_and_get(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "alert_repo_6",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        updated = self.repo.resolve_alert("tenant_b", "alert_repo_6", "2026-03-25T22:05:00Z")
        self.assertFalse(updated)

        wrong_tenant_view = self.repo.get_alert_by_id("tenant_b", "alert_repo_6")
        self.assertIsNone(wrong_tenant_view)

        original_tenant_view = self.repo.get_alert_by_id("tenant_a", "alert_repo_6")
        self.assertIsNotNone(original_tenant_view)
        self.assertEqual(original_tenant_view["status"], "open")

    def test_missing_required_field_handled_cleanly(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.create_alert(
                {
                    "ops_alert_id": "alert_repo_7",
                    "alert_type": "booking_failure",
                    "status": "open",
                }
            )

        missing_row_result = self.repo.resolve_alert(
            "tenant_x", "does_not_exist", "2026-03-25T22:10:00Z"
        )
        self.assertFalse(missing_row_result)


if __name__ == "__main__":
    unittest.main()
