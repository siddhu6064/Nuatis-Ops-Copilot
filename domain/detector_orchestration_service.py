"""Minimal orchestration service for running detector(s) over one event."""

from __future__ import annotations

from typing import Any

from workers.detectors.booking_failure_high_severity_detector import (
    BookingFailureHighSeverityDetector,
)


class DetectorOrchestrationService:
    def __init__(self, booking_failure_detector: BookingFailureHighSeverityDetector) -> None:
        self._detectors: list[tuple[str, Any]] = [
            ("booking_failure_high_severity", booking_failure_detector)
        ]

    def evaluate_event(self, activity_event: dict[str, Any]) -> dict[str, Any]:
        if not activity_event.get("tenant_id"):
            raise ValueError("tenant_id is required")

        results: list[dict[str, Any]] = []
        matches = 0
        alerts_created = 0

        for detector_name, detector in self._detectors:
            detector_result = detector.evaluate_event(activity_event)
            result = {
                "detector": detector_name,
                "result": detector_result.get("result", "no_match"),
            }
            if detector_result.get("ops_alert_id"):
                result["ops_alert_id"] = detector_result["ops_alert_id"]

            if result["result"] == "matched":
                matches += 1
                alerts_created += 1

            results.append(result)

        return {
            "tenant_id": activity_event["tenant_id"],
            "detectors_run": len(self._detectors),
            "matches": matches,
            "alerts_created": alerts_created,
            "results": results,
        }
