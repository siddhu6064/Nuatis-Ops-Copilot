import unittest
from pathlib import Path

from db.connection import connect, disconnect
from domain.ops_alerts_read_service import OpsAlertsReadService
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class OpsAlertsReadServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.service = OpsAlertsReadService(self.repo)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_list_alerts_with_filters_and_pagination(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "a1",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "open",
            }
        )
        self.repo.create_alert(
            {
                "ops_alert_id": "a2",
                "tenant_id": "tenant_a",
                "alert_type": "booking_failure",
                "status": "resolved",
            }
        )

        result = self.service.list_alerts(
            tenant_id="tenant_a", status="open", limit="10", offset="0"
        )

        self.assertEqual(result["tenant_id"], "tenant_a")
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["alerts"][0]["ops_alert_id"], "a1")

    def test_get_alert_tenant_scoped(self) -> None:
        self.repo.create_alert(
            {
                "ops_alert_id": "a3",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        found = self.service.get_alert(tenant_id="tenant_a", ops_alert_id="a3")
        missing = self.service.get_alert(tenant_id="tenant_b", ops_alert_id="a3")

        self.assertIsNotNone(found)
        self.assertIsNone(missing)

    def test_invalid_limit_raises_validation_error(self) -> None:
        with self.assertRaises(ValueError):
            self.service.list_alerts(tenant_id="tenant_a", limit="bad")

    def test_missing_tenant_id_raises_validation_error(self) -> None:
        with self.assertRaises(ValueError):
            self.service.list_alerts(tenant_id=None)
