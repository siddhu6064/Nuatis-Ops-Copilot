"""Minimal service layer for ops alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.timestamp_validation import is_valid_iso8601
from repositories.ops_alerts_repository import OpsAlertsRepository


class OpsAlertsService:
    REQUIRED_CREATE_FIELDS = (
        "ops_alert_id",
        "tenant_id",
        "alert_type",
        "status",
    )

    def __init__(self, repository: OpsAlertsRepository) -> None:
        self._repository = repository

    def create_ops_alert(self, alert_data: dict[str, Any]) -> dict[str, Any]:
        missing = [field for field in self.REQUIRED_CREATE_FIELDS if not alert_data.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        dedup_candidate = self._find_dedup_candidate(alert_data)
        if dedup_candidate is not None:
            return {
                "ops_alert_id": dedup_candidate["ops_alert_id"],
                "tenant_id": dedup_candidate["tenant_id"],
                "status": dedup_candidate["status"],
                "result": "deduped",
            }

        self._repository.create_alert(alert_data)

        return {
            "ops_alert_id": alert_data["ops_alert_id"],
            "tenant_id": alert_data["tenant_id"],
            "status": alert_data["status"],
            "result": "created",
        }

    def resolve_ops_alert(
        self,
        tenant_id: str,
        ops_alert_id: str,
        resolved_at: str | None = None,
    ) -> bool:
        if not tenant_id or not ops_alert_id:
            raise ValueError("tenant_id and ops_alert_id are required")

        if resolved_at is not None and not is_valid_iso8601(resolved_at):
            raise ValueError("resolved_at must be a valid ISO-8601 timestamp.")

        timestamp = resolved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return self._repository.resolve_alert(
            tenant_id=tenant_id,
            ops_alert_id=ops_alert_id,
            resolved_at=timestamp,
        )

    def _find_dedup_candidate(self, alert_data: dict[str, Any]) -> dict[str, Any] | None:
        if alert_data.get("alert_type") != "booking_failure_high_severity":
            return None

        source_event_id = alert_data.get("source_event_id")
        if not source_event_id:
            return None

        return self._repository.find_open_alert_by_dedup_key(
            tenant_id=alert_data["tenant_id"],
            alert_type=alert_data["alert_type"],
            source_event_id=source_event_id,
        )
