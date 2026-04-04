import unittest

from workers.detectors.call_failure_high_severity_detector import (
    CallFailureHighSeverityDetector,
)


class CallFailureHighSeverityDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = CallFailureHighSeverityDetector()

    def test_matching_event_returns_detector_result(self) -> None:
        result = self.detector.evaluate(
            {
                "activity_event_id": "call_act_1",
                "tenant_id": "tenant_a",
                "event_id": "call_evt_1",
                "event_type": "call.failed",
                "payload_json": '{"severity":"high","provider":"telephony"}',
            }
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "call_failure_high_severity")
        self.assertEqual(result.dedup_key, "call_evt_1")
        self.assertEqual(result.detector_name, "call_failure_high_severity")

    def test_non_matching_event_returns_none(self) -> None:
        result = self.detector.evaluate(
            {
                "activity_event_id": "call_act_2",
                "tenant_id": "tenant_a",
                "event_id": "call_evt_2",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high"}',
            }
        )

        self.assertIsNone(result)
