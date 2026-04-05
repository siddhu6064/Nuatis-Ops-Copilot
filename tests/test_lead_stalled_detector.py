import unittest

from workers.detectors.lead_stalled_detector import LeadStalledDetector


class LeadStalledDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LeadStalledDetector()

    def _base_event(self, **overrides) -> dict:
        event = {
            "activity_event_id": "act_ls_1",
            "tenant_id": "tenant_a",
            "event_id": "evt_ls_1",
            "event_type": "lead.stalled",
            "payload_json": '{"severity":"high","days_stalled":3}',
        }
        event.update(overrides)
        return event

    def test_no_match_wrong_event_type(self) -> None:
        result = self.detector.evaluate(self._base_event(event_type="booking.failed"))
        self.assertIsNone(result)

    def test_no_match_severity_not_high(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"low","days_stalled":5}')
        )
        self.assertIsNone(result)

    def test_no_match_severity_missing(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"days_stalled":5}')
        )
        self.assertIsNone(result)

    def test_no_match_days_stalled_too_low(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":2}')
        )
        self.assertIsNone(result)

    def test_no_match_days_stalled_zero(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":0}')
        )
        self.assertIsNone(result)

    def test_matched_created_returns_detector_result(self) -> None:
        result = self.detector.evaluate(self._base_event())
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "lead_stalled_high_severity")
        self.assertEqual(result.dedup_key, "evt_ls_1")
        self.assertEqual(result.detector_name, "lead_stalled_high_severity")
        self.assertEqual(result.severity, "high")

    def test_matched_at_boundary_days_stalled_equals_3(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":3}')
        )
        self.assertIsNotNone(result)

    def test_matched_high_days_stalled(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":30}')
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "lead_stalled_high_severity")

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        result = self.detector.evaluate(
            self._base_event(
                payload_json='{"severity":"high","days_stalled":5,"source_event_id":"src_ls_99"}'
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dedup_key, "src_ls_99")

    def test_evaluate_is_idempotent_same_event_returns_same_result(self) -> None:
        event = self._base_event()
        first = self.detector.evaluate(event)
        second = self.detector.evaluate(event)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.alert_type, second.alert_type)
        self.assertEqual(first.dedup_key, second.dedup_key)

    def test_required_input_handling_raises_on_missing_event_id(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_ls_err",
                    "tenant_id": "tenant_a",
                    "event_type": "lead.stalled",
                    "payload_json": '{"severity":"high","days_stalled":3}',
                }
            )
