import unittest
from pathlib import Path

from db.connection import connect, disconnect
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository
from workers.detectors.booking_failure_high_severity_detector import (
    BookingFailureHighSeverityDetector,
)


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class BookingFailureHighSeverityDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.service = OpsAlertsService(self.repo)
        self.detector = BookingFailureHighSeverityDetector(self.service)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_matching_event_creates_alert(self) -> None:
        result = self.detector.evaluate_event(
            {
                "activity_event_id": "act_1",
                "tenant_id": "tenant_a",
                "event_id": "evt_1",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high","reason":"provider_unavailable"}',
            }
        )

        self.assertEqual(result["result"], "matched_created")
        created = self.repo.get_alert_by_id("tenant_a", result["ops_alert_id"])
        self.assertIsNotNone(created)
        self.assertEqual(created["alert_type"], "booking_failure_high_severity")

    def test_non_matching_event_creates_no_alert(self) -> None:
        result = self.detector.evaluate_event(
            {
                "activity_event_id": "act_2",
                "tenant_id": "tenant_a",
                "event_id": "evt_2",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"low"}',
            }
        )

        self.assertEqual(result, {"result": "no_match"})
        tenant_alerts = self.repo.list_alerts_by_tenant("tenant_a")
        self.assertEqual(len(tenant_alerts), 0)

    def test_tenant_scoped_alert_creation_is_preserved(self) -> None:
        first = self.detector.evaluate_event(
            {
                "activity_event_id": "act_3",
                "tenant_id": "tenant_alpha",
                "event_id": "evt_3",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )
        second = self.detector.evaluate_event(
            {
                "activity_event_id": "act_4",
                "tenant_id": "tenant_beta",
                "event_id": "evt_4",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )

        alpha_alert = self.repo.get_alert_by_id("tenant_alpha", first["ops_alert_id"])
        beta_alert = self.repo.get_alert_by_id("tenant_beta", second["ops_alert_id"])
        cross_tenant = self.repo.get_alert_by_id("tenant_alpha", second["ops_alert_id"])

        self.assertIsNotNone(alpha_alert)
        self.assertIsNotNone(beta_alert)
        self.assertIsNone(cross_tenant)

    def test_required_input_handling_is_covered(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate_event(
                {
                    "activity_event_id": "act_5",
                    "tenant_id": "tenant_a",
                    "event_type": "booking.failed",
                    "payload_json": '{"severity":"high"}',
                }
            )
