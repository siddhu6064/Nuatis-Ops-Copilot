"""First minimal detector rule for ops alerts."""

from __future__ import annotations

import json
from typing import Any

from domain.ops_alerts_service import OpsAlertsService


class BookingFailureHighSeverityDetector:
    """Creates an ops alert for high-severity booking failures."""

    def __init__(self, alerts_service: OpsAlertsService) -> None:
        self._alerts_service = alerts_service

    def evaluate_event(self, activity_event: dict[str, Any]) -> dict[str, Any]:
        required = ("activity_event_id", "tenant_id", "event_id", "event_type", "payload_json")
        missing = [field for field in required if not activity_event.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        payload = activity_event["payload_json"]
        payload_data = self._normalize_payload(payload)

        is_match = (
            activity_event["event_type"] == "booking.failed"
            and payload_data.get("severity") == "high"
        )

        if not is_match:
            return {"result": "no_match"}

        ops_alert_id = f"ops_alert_{activity_event['tenant_id']}_{activity_event['event_id']}"
        self._alerts_service.create_ops_alert(
            {
                "ops_alert_id": ops_alert_id,
                "tenant_id": activity_event["tenant_id"],
                "source_activity_event_id": activity_event["activity_event_id"],
                "source_event_id": activity_event["event_id"],
                "alert_type": "booking_failure_high_severity",
                "status": "open",
                "details_json": json.dumps(
                    {
                        "rule": "booking.failed + severity=high",
                        "event_type": activity_event["event_type"],
                    }
                ),
            }
        )

        return {"result": "matched", "ops_alert_id": ops_alert_id}

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
