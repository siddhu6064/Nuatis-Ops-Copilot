import unittest
from pathlib import Path

from db.connection import connect, disconnect
from api.activity_events_endpoint import _build_configured_notifier
from domain.detector_orchestration_service import DetectorOrchestrationService
from domain.notification_contracts import NotificationResult
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository
from workers.detectors.booking_failure_high_severity_detector import (
    BookingFailureHighSeverityDetector,
)
from workers.notifiers.webhook_notifier import WebhookNotifier

MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class SpyNotifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def notify(self, alert: dict) -> NotificationResult:
        self.calls.append(alert)
        return NotificationResult(success=True, message="sent")


class FailingNotifier:
    def notify(self, alert: dict) -> NotificationResult:
        raise RuntimeError("notify failed")


class RecordingTransport:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def send(self, webhook_url: str, payload: dict) -> NotificationResult:
        self.payloads.append({"url": webhook_url, "payload": payload})
        return NotificationResult(success=True)


class AlertNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.alert_service = OpsAlertsService(self.repo)

    def tearDown(self) -> None:
        disconnect(self.db)

    def _event(self, event_id: str) -> dict:
        return {
            "activity_event_id": f"act_{event_id}",
            "tenant_id": "tenant_a",
            "event_id": event_id,
            "event_type": "booking.failed",
            "payload_json": '{"severity":"high"}',
        }

    def test_newly_created_alert_triggers_notifier(self) -> None:
        spy = SpyNotifier()
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=spy)

        summary = orchestration.evaluate_event(self._event("evt_created"))

        self.assertEqual(summary["alerts_created"], 1)
        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(spy.calls[0]["ops_alert_id"], summary["results"][0]["ops_alert_id"])
        self.assertTrue(summary["results"][0]["notification"]["attempted"])
        self.assertTrue(summary["results"][0]["notification"]["success"])

    def test_deduped_alert_does_not_trigger_notifier(self) -> None:
        spy = SpyNotifier()
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=spy)

        orchestration.evaluate_event(self._event("evt_dup"))
        second = orchestration.evaluate_event(self._event("evt_dup"))

        self.assertEqual(second["alerts_deduped"], 1)
        self.assertEqual(len(spy.calls), 1)
        self.assertNotIn("notification", second["results"][0])

    def test_notifier_failure_is_isolated(self) -> None:
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=FailingNotifier())

        summary = orchestration.evaluate_event(self._event("evt_notify_fail"))

        self.assertEqual(summary["alerts_created"], 1)
        self.assertTrue(summary["results"][0]["notification"]["attempted"])
        self.assertFalse(summary["results"][0]["notification"]["success"])
        stored = self.repo.get_alert_by_id("tenant_a", summary["results"][0]["ops_alert_id"])
        self.assertIsNotNone(stored)

    def test_webhook_payload_contains_expected_alert_fields(self) -> None:
        transport = RecordingTransport()
        notifier = WebhookNotifier("https://example.test/webhook", transport)
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=notifier)

        summary = orchestration.evaluate_event(self._event("evt_payload"))

        self.assertEqual(summary["alerts_created"], 1)
        self.assertEqual(len(transport.payloads), 1)
        payload = transport.payloads[0]["payload"]
        self.assertEqual(payload["ops_alert_id"], summary["results"][0]["ops_alert_id"])
        self.assertEqual(payload["tenant_id"], "tenant_a")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["alert_type"], "booking_failure_high_severity")
        self.assertIn("created_at", payload)
        self.assertIn("details_json", payload)

    def test_notifications_disabled_results_in_no_notifier_attempt(self) -> None:
        notifier = _build_configured_notifier(False, "https://example.test/webhook")
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=notifier)

        summary = orchestration.evaluate_event(self._event("evt_disabled"))

        self.assertEqual(summary["alerts_created"], 1)
        self.assertFalse(summary["results"][0]["notification"]["attempted"])
        self.assertFalse(summary["results"][0]["notification"]["success"])

    def test_missing_webhook_url_results_in_noop_notifier_behavior(self) -> None:
        notifier = _build_configured_notifier(True, None)
        orchestration = DetectorOrchestrationService(self.alert_service, notifier=notifier)

        summary = orchestration.evaluate_event(self._event("evt_missing_url"))

        self.assertEqual(summary["alerts_created"], 1)
        self.assertFalse(summary["results"][0]["notification"]["attempted"])
        self.assertFalse(summary["results"][0]["notification"]["success"])


if __name__ == "__main__":
    unittest.main()
