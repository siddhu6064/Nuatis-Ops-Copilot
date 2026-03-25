"""Read service for tenant-scoped ops alert queries."""

from __future__ import annotations

from typing import Any

from domain.timestamp_validation import is_valid_iso8601
from repositories.ops_alerts_repository import OpsAlertsRepository


class OpsAlertsReadService:
    ALLOWED_STATUSES = ("open", "resolved")

    def __init__(self, repository: OpsAlertsRepository) -> None:
        self._repository = repository

    def list_alerts(
        self,
        *,
        tenant_id: str | None,
        limit: str | int | None = None,
        offset: str | int | None = None,
        status: str | None = None,
        alert_type: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> dict[str, Any]:
        if tenant_id is None or tenant_id == "":
            raise ValueError("tenant_id is required.")

        parsed_limit = self._parse_non_negative_int(limit, "limit", default=50)
        parsed_offset = self._parse_non_negative_int(offset, "offset", default=0)
        normalized_status = self._normalize_optional(status)

        normalized_created_from = self._normalize_optional(created_from)
        normalized_created_to = self._normalize_optional(created_to)
        if normalized_status is not None and normalized_status not in self.ALLOWED_STATUSES:
            raise ValueError("status must be one of: open, resolved")

        if normalized_created_from is not None and not is_valid_iso8601(normalized_created_from):
            raise ValueError("created_from must be a valid ISO-8601 timestamp.")
        if normalized_created_to is not None and not is_valid_iso8601(normalized_created_to):
            raise ValueError("created_to must be a valid ISO-8601 timestamp.")

        alerts = self._repository.list_alerts_by_tenant(
            tenant_id,
            limit=parsed_limit,
            offset=parsed_offset,
            status=normalized_status,
            alert_type=self._normalize_optional(alert_type),
            created_from=normalized_created_from,
            created_to=normalized_created_to,
        )

        return {
            "tenant_id": tenant_id,
            "alerts": alerts,
            "pagination": {
                "limit": parsed_limit,
                "offset": parsed_offset,
            },
            "filters": {
                "status": normalized_status,
                "alert_type": self._normalize_optional(alert_type),
                "created_from": normalized_created_from,
                "created_to": normalized_created_to,
            },
        }

    def get_alert(self, *, tenant_id: str | None, ops_alert_id: str) -> dict[str, Any] | None:
        if tenant_id is None or tenant_id == "":
            raise ValueError("tenant_id is required.")

        return self._repository.get_alert_by_id(tenant_id, ops_alert_id)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped != "" else None

    @staticmethod
    def _parse_non_negative_int(value: str | int | None, field: str, *, default: int) -> int:
        if value is None or value == "":
            return default

        if isinstance(value, int):
            parsed = value
        else:
            try:
                parsed = int(value)
            except ValueError as exc:
                raise ValueError(f"{field} must be a non-negative integer.") from exc

        if parsed < 0:
            raise ValueError(f"{field} must be a non-negative integer.")

        return parsed
