import unittest
from pathlib import Path

from db.connection import connect, disconnect
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class OpsAlertsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.service = OpsAlertsService(self.repo)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_create_ops_alert_success(self) -> None:
        result = self.service.create_ops_alert(
            {
                "ops_alert_id": "svc_alert_1",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )

        self.assertEqual(result["ops_alert_id"], "svc_alert_1")
        stored = self.repo.get_alert_by_id("tenant_a", "svc_alert_1")
        self.assertIsNotNone(stored)

    def test_resolve_ops_alert_success(self) -> None:
        self.service.create_ops_alert(
            {
                "ops_alert_id": "svc_alert_2",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        resolved = self.service.resolve_ops_alert(
            tenant_id="tenant_a",
            ops_alert_id="svc_alert_2",
            resolved_at="2026-03-25T23:00:00Z",
        )

        self.assertTrue(resolved)
        stored = self.repo.get_alert_by_id("tenant_a", "svc_alert_2")
        self.assertEqual(stored["status"], "resolved")

    def test_resolve_ops_alert_missing_row_returns_false(self) -> None:
        resolved = self.service.resolve_ops_alert(
            tenant_id="tenant_x",
            ops_alert_id="missing_alert",
            resolved_at="2026-03-25T23:05:00Z",
        )

        self.assertFalse(resolved)

    def test_tenant_scoped_behavior_is_preserved(self) -> None:
        self.service.create_ops_alert(
            {
                "ops_alert_id": "svc_alert_3",
                "tenant_id": "tenant_a",
                "alert_type": "stale_contact",
                "status": "open",
            }
        )

        wrong_tenant_resolve = self.service.resolve_ops_alert(
            tenant_id="tenant_b",
            ops_alert_id="svc_alert_3",
            resolved_at="2026-03-25T23:10:00Z",
        )

        self.assertFalse(wrong_tenant_resolve)
        tenant_a_alert = self.repo.get_alert_by_id("tenant_a", "svc_alert_3")
        self.assertEqual(tenant_a_alert["status"], "open")
        tenant_b_alert = self.repo.get_alert_by_id("tenant_b", "svc_alert_3")
        self.assertIsNone(tenant_b_alert)

    def test_required_input_handling_is_covered(self) -> None:
        with self.assertRaises(ValueError):
            self.service.create_ops_alert(
                {
                    "ops_alert_id": "svc_alert_4",
                    "alert_type": "booking_failure",
                    "status": "open",
                }
            )

        with self.assertRaises(ValueError):
            self.service.resolve_ops_alert(
                tenant_id="",
                ops_alert_id="svc_alert_4",
                resolved_at="2026-03-25T23:20:00Z",
            )


if __name__ == "__main__":
    unittest.main()
