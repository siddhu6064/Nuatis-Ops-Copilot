"""Minimal orchestration service for running detector(s) over one event."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import Detector
from domain.ops_alerts_service import OpsAlertsService
from workers.detectors.booking_failure_high_severity_detector import BookingFailureHighSeverityDetector


DETECTOR_REGISTRY: list[tuple[str, Detector]] = [
    ("booking_failure_high_severity", BookingFailureHighSeverityDetector()),
]


class DetectorOrchestrationService:
    def __init__(
        self,
        alerts_service: OpsAlertsService,
        detector_registry: list[tuple[str, Detector]] | None = None,
    ) -> None:
        self._alerts_service = alerts_service
        self._detectors = detector_registry or DETECTOR_REGISTRY

    def evaluate_event(self, activity_event: dict[str, Any]) -> dict[str, Any]:
        if not activity_event.get("tenant_id"):
            raise ValueError("tenant_id is required")
        if not activity_event.get("activity_event_id"):
            raise ValueError("activity_event_id is required")

        results: list[dict[str, Any]] = []
        matches = 0
        alerts_created = 0
        alerts_deduped = 0

        for detector_name, detector in self._detectors:
            detector_result = detector.evaluate(activity_event)
            result_type = "no_match"
            result = {
                "detector": detector_name,
                "result": "no_match",
            }

            if detector_result is not None:
                create_result = self._alerts_service.create_ops_alert(
                    {
                        "ops_alert_id": f"ops_alert_{activity_event['tenant_id']}_{detector_result.dedup_key}",
                        "tenant_id": activity_event["tenant_id"],
                        "source_activity_event_id": activity_event["activity_event_id"],
                        "source_event_id": detector_result.dedup_key,
                        "alert_type": detector_result.alert_type,
                        "status": "open",
                        "details_json": json.dumps(
                            {
                                "payload": detector_result.payload,
                                "severity": detector_result.severity,
                                "metadata": detector_result.metadata or {},
                            }
                        ),
                    }
                )
                result_type = "matched_created" if create_result["result"] == "created" else "matched_deduped"
                result["result"] = result_type
                result["ops_alert_id"] = create_result["ops_alert_id"]
                matches += 1
                if result_type == "matched_created":
                    alerts_created += 1
                else:
                    alerts_deduped += 1

            results.append(result)

        return {
            "tenant_id": activity_event["tenant_id"],
            "detectors_run": len(self._detectors),
            "matches": matches,
            "alerts_created": alerts_created,
            "alerts_deduped": alerts_deduped,
            "results": results,
        }
