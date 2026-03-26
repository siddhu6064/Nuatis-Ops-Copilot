"""Read service for tenant-scoped ops alert queries."""

from __future__ import annotations

from typing import Any

from domain.alert_query_params import AlertQueryParams
from domain.timestamp_validation import is_valid_iso8601
from repositories.ops_alerts_repository import OpsAlertsRepository


class OpsAlertsReadService:
    ALLOWED_STATUSES = ("open", "resolved")
    ALLOWED_SORT_ORDERS = ("asc", "desc")
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    def __init__(self, repository: OpsAlertsRepository) -> None:
        self._repository = repository

    def list_alerts(
        self,
        params: AlertQueryParams,
    ) -> dict[str, Any]:
        if params.tenant_id == "":
            raise ValueError("tenant_id is required.")

        normalized_status = self._normalize_optional(params.status)
        normalized_created_after = self._normalize_optional(params.created_after)
        normalized_created_before = self._normalize_optional(params.created_before)
        normalized_sort_order = self._normalize_sort_order(params.sort_order)
        normalized_limit = self._normalize_limit(params.limit)
        normalized_offset = self._parse_non_negative_int(params.offset, "offset", default=0)

        if normalized_status is not None and normalized_status not in self.ALLOWED_STATUSES:
            raise ValueError("status must be one of: open, resolved")

        if normalized_created_after is not None and not is_valid_iso8601(normalized_created_after):
            raise ValueError("created_after must be a valid ISO-8601 timestamp.")
        if normalized_created_before is not None and not is_valid_iso8601(normalized_created_before):
            raise ValueError("created_before must be a valid ISO-8601 timestamp.")

        alerts = self._repository.list_alerts_by_tenant(
            params.tenant_id,
            limit=normalized_limit,
            offset=normalized_offset,
            status=normalized_status,
            created_after=normalized_created_after,
            created_before=normalized_created_before,
            sort_order=normalized_sort_order,
        )

        return {
            "tenant_id": params.tenant_id,
            "alerts": alerts,
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
            },
            "filters": {
                "status": normalized_status,
                "created_after": normalized_created_after,
                "created_before": normalized_created_before,
                "sort_order": normalized_sort_order,
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

    def _normalize_limit(self, value: str | int | None) -> int:
        parsed = self._parse_non_negative_int(value, "limit", default=self.DEFAULT_LIMIT)
        return min(parsed, self.MAX_LIMIT)

    def _normalize_sort_order(self, value: str | None) -> str:
        normalized = self._normalize_optional(value) or "desc"
        if normalized not in self.ALLOWED_SORT_ORDERS:
            raise ValueError("sort_order must be one of: asc, desc")
        return normalized
