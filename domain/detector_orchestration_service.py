"""Minimal orchestration service for running detector(s) over one event."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import Detector
from domain.notification_contracts import Notifier
from domain.ops_alerts_service import OpsAlertsService
from workers.detectors.booking_failure_high_severity_detector import BookingFailureHighSeverityDetector
from workers.detectors.call_failure_high_severity_detector import CallFailureHighSeverityDetector


DETECTOR_REGISTRY: list[tuple[str, Detector]] = [
    ("booking_failure_high_severity", BookingFailureHighSeverityDetector()),
    ("call_failure_high_severity", CallFailureHighSeverityDetector()),
]


class DetectorOrchestrationService:
    def __init__(
        self,
        alerts_service: OpsAlertsService,
        detector_registry: list[tuple[str, Detector]] | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self._alerts_service = alerts_service
        self._detectors = detector_registry or DETECTOR_REGISTRY
        self._notifier = notifier

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
            result = {
                "detector": detector_name,
                "result": "no_match",
                "outcome": "no_match",
                "evaluated": True,
            }
            detector_result = None

            try:
                detector_result = detector.evaluate(activity_event)
            except Exception as exc:  # noqa: BLE001 - detector errors are isolated by design
                result["result"] = "error"
                result["outcome"] = "error"
                result["error"] = str(exc)
                results.append(result)
                continue

            if detector_result is not None:
                attributed_detector_name = detector_result.detector_name or detector_name
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
                                "detector_name": attributed_detector_name,
                                "metadata": detector_result.metadata or {},
                            }
                        ),
                    }
                )
                is_created = create_result["result"] == "created"
                result["result"] = "matched_created" if is_created else "matched_deduped"
                result["outcome"] = "created" if is_created else "deduped"
                result["ops_alert_id"] = create_result["ops_alert_id"]
                result["alert_type"] = detector_result.alert_type
                matches += 1
                if is_created:
                    alerts_created += 1
                    result["notification"] = {
                        "attempted": False,
                        "success": False,
                        "message": "notifier_not_configured",
                    }
                    if self._notifier is not None:
                        try:
                            created_alert = self._alerts_service.get_ops_alert(
                                tenant_id=activity_event["tenant_id"],
                                ops_alert_id=create_result["ops_alert_id"],
                            )
                            if created_alert is not None:
                                notification_result = self._notifier.notify(created_alert)
                                result["notification"] = {
                                    "attempted": True,
                                    "success": notification_result.success,
                                    "message": notification_result.message,
                                }
                        except Exception as exc:  # noqa: BLE001 - notification must not break alert flow
                            result["notification"] = {
                                "attempted": True,
                                "success": False,
                                "message": str(exc),
                            }
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
