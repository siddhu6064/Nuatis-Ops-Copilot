"""Detector rule for high-severity call failures."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import DetectorResult


class CallFailureHighSeverityDetector:
    """Returns a detector result for high-severity call failures."""

    def evaluate(self, activity_event: dict[str, Any]) -> DetectorResult | None:
        required = ("activity_event_id", "tenant_id", "event_id", "event_type", "payload_json")
        missing = [field for field in required if not activity_event.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        payload_data = self._normalize_payload(activity_event["payload_json"])
        is_match = activity_event["event_type"] == "call.failed" and payload_data.get("severity") == "high"
        if not is_match:
            return None

        source_event_id = str(payload_data.get("source_event_id") or activity_event["event_id"])
        severity = payload_data.get("severity")
        if severity is not None:
            severity = str(severity)

        return DetectorResult(
            alert_type="call_failure_high_severity",
            dedup_key=source_event_id,
            detector_name="call_failure_high_severity",
            payload={
                "rule": "call.failed + severity=high",
                "event_type": activity_event["event_type"],
            },
            severity=severity,
            metadata={
                "source_event_id": source_event_id,
                "payload_json": payload_data,
            },
        )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}

        return {}
