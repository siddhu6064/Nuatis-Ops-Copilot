import unittest

from workers.detectors.appointment_no_show_detector import AppointmentNoShowDetector


class AppointmentNoShowDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = AppointmentNoShowDetector()

    def _base_event(self, **overrides) -> dict:
        event = {
            "activity_event_id": "act_ans_1",
            "tenant_id": "tenant_a",
            "event_id": "evt_ans_1",
            "event_type": "appointment.no_show",
            "payload_json": '{"severity":"high"}',
        }
        event.update(overrides)
        return event

    def test_no_match_wrong_event_type(self) -> None:
        result = self.detector.evaluate(self._base_event(event_type="call.failed"))
        self.assertIsNone(result)

    def test_no_match_severity_not_high(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"medium"}')
        )
        self.assertIsNone(result)

    def test_no_match_severity_missing(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"reason":"client_cancelled"}')
        )
        self.assertIsNone(result)

    def test_matched_created_returns_detector_result(self) -> None:
        result = self.detector.evaluate(self._base_event())
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "appointment_no_show_high_severity")
        self.assertEqual(result.dedup_key, "evt_ans_1")
        self.assertEqual(result.detector_name, "appointment_no_show_high_severity")
        self.assertEqual(result.severity, "high")

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        result = self.detector.evaluate(
            self._base_event(
                payload_json='{"severity":"high","source_event_id":"src_ans_99"}'
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dedup_key, "src_ans_99")

    def test_evaluate_is_idempotent_same_event_returns_same_result(self) -> None:
        event = self._base_event()
        first = self.detector.evaluate(event)
        second = self.detector.evaluate(event)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.alert_type, second.alert_type)
        self.assertEqual(first.dedup_key, second.dedup_key)

    def test_matched_created_again_evaluate_is_stateless(self) -> None:
        event = self._base_event()
        for _ in range(3):
            result = self.detector.evaluate(event)
            self.assertIsNotNone(result)
            self.assertEqual(result.alert_type, "appointment_no_show_high_severity")

    def test_required_input_handling_raises_on_missing_event_id(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_ans_err",
                    "tenant_id": "tenant_a",
                    "event_type": "appointment.no_show",
                    "payload_json": '{"severity":"high"}',
                }
            )
