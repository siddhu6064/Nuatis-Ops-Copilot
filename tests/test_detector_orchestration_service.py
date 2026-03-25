import unittest
from pathlib import Path

from db.connection import connect, disconnect
from domain.detector_contracts import DetectorResult
from domain.detector_orchestration_service import DetectorOrchestrationService
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class DetectorOrchestrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)
        self.alert_service = OpsAlertsService(self.repo)
        self.orchestrator = DetectorOrchestrationService(self.alert_service)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_matching_event_produces_one_match_and_one_alert(self) -> None:
        summary = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_1",
                "tenant_id": "tenant_a",
                "event_id": "or_evt_1",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )

        self.assertEqual(summary["detectors_run"], 1)
        self.assertEqual(summary["matches"], 1)
        self.assertEqual(summary["alerts_created"], 1)
        self.assertEqual(summary["alerts_deduped"], 0)
        self.assertEqual(summary["results"][0]["result"], "matched_created")

        alert_id = summary["results"][0]["ops_alert_id"]
        stored = self.repo.get_alert_by_id("tenant_a", alert_id)
        self.assertIsNotNone(stored)

    def test_non_matching_event_produces_zero_matches(self) -> None:
        summary = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_2",
                "tenant_id": "tenant_a",
                "event_id": "or_evt_2",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"low"}',
            }
        )

        self.assertEqual(summary["detectors_run"], 1)
        self.assertEqual(summary["matches"], 0)
        self.assertEqual(summary["alerts_created"], 0)
        self.assertEqual(summary["alerts_deduped"], 0)
        self.assertEqual(summary["results"][0]["result"], "no_match")

    def test_detector_returning_none_creates_no_alert(self) -> None:
        class NoopDetector:
            def evaluate(self, event: dict) -> None:
                return None

        orchestrator = DetectorOrchestrationService(
            self.alert_service,
            detector_registry=[("noop_detector", NoopDetector())],
        )
        summary = orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_none",
                "tenant_id": "tenant_a",
                "event_id": "or_evt_none",
                "event_type": "call.completed",
                "payload_json": "{}",
            }
        )
        self.assertEqual(summary["matches"], 0)
        self.assertEqual(summary["alerts_created"], 0)
        self.assertEqual(len(self.repo.list_alerts_by_tenant("tenant_a")), 0)

    def test_orchestration_preserves_tenant_scoped_behavior(self) -> None:
        alpha = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_3",
                "tenant_id": "tenant_alpha",
                "event_id": "or_evt_3",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )
        beta = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_4",
                "tenant_id": "tenant_beta",
                "event_id": "or_evt_4",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )

        alpha_alert = self.repo.get_alert_by_id("tenant_alpha", alpha["results"][0]["ops_alert_id"])
        beta_alert = self.repo.get_alert_by_id("tenant_beta", beta["results"][0]["ops_alert_id"])
        cross_tenant = self.repo.get_alert_by_id("tenant_alpha", beta["results"][0]["ops_alert_id"])

        self.assertEqual(alpha["tenant_id"], "tenant_alpha")
        self.assertEqual(beta["tenant_id"], "tenant_beta")
        self.assertIsNotNone(alpha_alert)
        self.assertIsNotNone(beta_alert)
        self.assertIsNone(cross_tenant)

    def test_required_input_handling_is_covered(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.evaluate_event(
                {
                    "activity_event_id": "or_act_5",
                    "event_id": "or_evt_5",
                    "event_type": "booking.failed",
                    "payload_json": '{"severity":"high"}',
                }
            )

    def test_second_matching_event_is_deduped(self) -> None:
        first = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_6",
                "tenant_id": "tenant_a",
                "event_id": "same_evt",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )
        second = self.orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_7",
                "tenant_id": "tenant_a",
                "event_id": "same_evt",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )

        self.assertEqual(first["results"][0]["result"], "matched_created")
        self.assertEqual(second["results"][0]["result"], "matched_deduped")
        self.assertEqual(second["alerts_created"], 0)
        self.assertEqual(second["alerts_deduped"], 1)
        self.assertEqual(len(self.repo.list_alerts_by_tenant("tenant_a")), 1)

    def test_multiple_detectors_only_matching_detector_fires(self) -> None:
        class NoopDetector:
            def evaluate(self, event: dict) -> None:
                return None

        class MatchingDetector:
            def evaluate(self, event: dict) -> DetectorResult:
                return DetectorResult(
                    alert_type="booking_failure_high_severity",
                    dedup_key=event["event_id"],
                    payload={"rule": "match-all"},
                )

        orchestrator = DetectorOrchestrationService(
            self.alert_service,
            detector_registry=[
                ("noop_detector", NoopDetector()),
                ("matching_detector", MatchingDetector()),
            ],
        )
        summary = orchestrator.evaluate_event(
            {
                "activity_event_id": "or_act_multi",
                "tenant_id": "tenant_multi",
                "event_id": "evt_multi",
                "event_type": "booking.failed",
                "payload_json": "{}",
            }
        )

        self.assertEqual(summary["detectors_run"], 2)
        self.assertEqual(summary["matches"], 1)
        self.assertEqual(summary["alerts_created"], 1)
        self.assertEqual(summary["results"][0]["result"], "no_match")
        self.assertEqual(summary["results"][1]["result"], "matched_created")
