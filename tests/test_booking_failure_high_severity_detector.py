import unittest

from workers.detectors.booking_failure_high_severity_detector import (
    BookingFailureHighSeverityDetector,
)

class BookingFailureHighSeverityDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = BookingFailureHighSeverityDetector()

    def test_matching_event_returns_detector_result(self) -> None:
        result = self.detector.evaluate(
            {
                "activity_event_id": "act_1",
                "tenant_id": "tenant_a",
                "event_id": "evt_1",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high","reason":"provider_unavailable"}',
            }
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "booking_failure_high_severity")
        self.assertEqual(result.dedup_key, "evt_1")
        self.assertEqual(result.detector_name, "booking_failure_high_severity")
        self.assertEqual(result.severity, "high")

    def test_non_matching_event_returns_none(self) -> None:
        result = self.detector.evaluate(
            {
                "activity_event_id": "act_2",
                "tenant_id": "tenant_a",
                "event_id": "evt_2",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"low"}',
            }
        )

        self.assertIsNone(result)

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        first = self.detector.evaluate(
            {
                "activity_event_id": "act_3",
                "tenant_id": "tenant_alpha",
                "event_id": "evt_3",
                "event_type": "booking.failed",
                "payload_json": '{"severity":"high","source_event_id":"src_99"}',
            }
        )
        self.assertIsNotNone(first)
        self.assertEqual(first.dedup_key, "src_99")

    def test_required_input_handling_is_covered(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_5",
                    "tenant_id": "tenant_a",
                    "event_type": "booking.failed",
                    "payload_json": '{"severity":"high"}',
                }
            )
