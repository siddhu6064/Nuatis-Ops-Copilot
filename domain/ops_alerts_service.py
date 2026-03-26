"""Minimal service layer for ops alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.internal_event_contracts import EventPublishResult, InternalEvent, InternalEventPublisher
from domain.timestamp_validation import is_valid_iso8601
from repositories.ops_alerts_repository import OpsAlertsRepository


class OpsAlertsService:
    ALLOWED_STATUSES = ("open", "resolved")
    REQUIRED_CREATE_FIELDS = (
        "ops_alert_id",
        "tenant_id",
        "alert_type",
        "status",
    )

    def __init__(
        self,
        repository: OpsAlertsRepository,
        event_publisher: InternalEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def create_ops_alert(self, alert_data: dict[str, Any]) -> dict[str, Any]:
        missing = [field for field in self.REQUIRED_CREATE_FIELDS if not alert_data.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        if alert_data["status"] not in self.ALLOWED_STATUSES:
            raise ValueError("status must be one of: open, resolved")

        dedup_candidate = self._find_dedup_candidate(alert_data)
        if dedup_candidate is not None:
            return {
                "ops_alert_id": dedup_candidate["ops_alert_id"],
                "tenant_id": dedup_candidate["tenant_id"],
                "status": dedup_candidate["status"],
                "result": "deduped",
            }

        self._repository.create_alert(alert_data)
        self._publish_internal_event(
            InternalEvent(
                event_type="alert_created",
                payload={
                    "ops_alert_id": alert_data["ops_alert_id"],
                    "tenant_id": alert_data["tenant_id"],
                    "alert_type": alert_data["alert_type"],
                    "status": alert_data["status"],
                    "source_event_id": alert_data.get("source_event_id"),
                    "source_activity_event_id": alert_data.get("source_activity_event_id"),
                },
            )
        )

        return {
            "ops_alert_id": alert_data["ops_alert_id"],
            "tenant_id": alert_data["tenant_id"],
            "status": alert_data["status"],
            "result": "created",
        }

    def get_ops_alert(self, *, tenant_id: str, ops_alert_id: str) -> dict[str, Any] | None:
        if not tenant_id or not ops_alert_id:
            raise ValueError("tenant_id and ops_alert_id are required")
        return self._repository.get_alert_by_id(tenant_id, ops_alert_id)

    def resolve_ops_alert(
        self,
        tenant_id: str,
        ops_alert_id: str,
        resolved_at: str | None = None,
        resolved_by: str | None = None,
    ) -> bool:
        if not tenant_id or not ops_alert_id:
            raise ValueError("tenant_id and ops_alert_id are required")

        if resolved_at is not None and not is_valid_iso8601(resolved_at):
            raise ValueError("resolved_at must be a valid ISO-8601 timestamp.")

        if resolved_by is not None and not isinstance(resolved_by, str):
            raise ValueError("resolved_by must be a string when provided.")
        if isinstance(resolved_by, str) and resolved_by.strip() == "":
            raise ValueError("resolved_by must be a non-empty string when provided.")

        existing = self._repository.get_alert_by_id(tenant_id, ops_alert_id)

        timestamp = resolved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        resolved = self._repository.resolve_alert(
            tenant_id=tenant_id,
            ops_alert_id=ops_alert_id,
            resolved_at=timestamp,
            resolved_by=resolved_by,
        )
        if resolved and existing is not None and existing["status"] == "open":
            self._publish_internal_event(
                InternalEvent(
                    event_type="alert_resolved",
                    payload={
                        "ops_alert_id": ops_alert_id,
                        "tenant_id": tenant_id,
                        "resolved_at": timestamp,
                        "resolved_by": resolved_by,
                    },
                )
            )
        return resolved

    def bulk_resolve_ops_alerts(
        self,
        *,
        tenant_id: str,
        ops_alert_ids: list[str],
        resolved_at: str | None = None,
        resolved_by: str | None = None,
    ) -> dict[str, Any]:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not isinstance(ops_alert_ids, list) or len(ops_alert_ids) == 0:
            raise ValueError("ops_alert_ids must be a non-empty list.")

        normalized_ids: list[str] = []
        for ops_alert_id in ops_alert_ids:
            if not isinstance(ops_alert_id, str) or ops_alert_id.strip() == "":
                raise ValueError("ops_alert_ids must contain non-empty strings.")
            normalized_ids.append(ops_alert_id)

        if resolved_at is not None and not is_valid_iso8601(resolved_at):
            raise ValueError("resolved_at must be a valid ISO-8601 timestamp.")
        if resolved_by is not None and not isinstance(resolved_by, str):
            raise ValueError("resolved_by must be a string when provided.")
        if isinstance(resolved_by, str) and resolved_by.strip() == "":
            raise ValueError("resolved_by must be a non-empty string when provided.")

        timestamp = resolved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        unique_ids = list(dict.fromkeys(normalized_ids))

        resolved_count = 0
        already_resolved_count = 0
        not_found_count = 0
        results: list[dict[str, str]] = []

        for ops_alert_id in unique_ids:
            existing = self._repository.get_alert_by_id(tenant_id, ops_alert_id)
            if existing is None:
                not_found_count += 1
                results.append({"ops_alert_id": ops_alert_id, "result": "not_found"})
                continue

            self._repository.resolve_alert(
                tenant_id=tenant_id,
                ops_alert_id=ops_alert_id,
                resolved_at=timestamp,
                resolved_by=resolved_by,
            )
            if existing["status"] == "resolved":
                already_resolved_count += 1
                results.append({"ops_alert_id": ops_alert_id, "result": "already_resolved"})
            else:
                self._publish_internal_event(
                    InternalEvent(
                        event_type="alert_resolved",
                        payload={
                            "ops_alert_id": ops_alert_id,
                            "tenant_id": tenant_id,
                            "resolved_at": timestamp,
                            "resolved_by": resolved_by,
                        },
                    )
                )
                resolved_count += 1
                results.append({"ops_alert_id": ops_alert_id, "result": "resolved"})

        return {
            "requested_count": len(normalized_ids),
            "resolved_count": resolved_count,
            "already_resolved_count": already_resolved_count,
            "not_found_count": not_found_count,
            "results": results,
        }

    def _find_dedup_candidate(self, alert_data: dict[str, Any]) -> dict[str, Any] | None:
        if alert_data.get("status") != "open":
            return None

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

    def _publish_internal_event(self, event: InternalEvent) -> EventPublishResult:
        if self._event_publisher is None:
            return EventPublishResult(success=False, message="publisher_not_configured")

        try:
            return self._event_publisher.publish(event)
        except Exception as exc:  # noqa: BLE001 - publisher failures must not break core alert flows
            return EventPublishResult(success=False, message=str(exc))
