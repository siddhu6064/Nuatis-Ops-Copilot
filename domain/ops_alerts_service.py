"""Minimal service layer for ops alerts."""

from __future__ import annotations

from typing import Any

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

        self._repository.create_alert(alert_data)

        return {
            "ops_alert_id": alert_data["ops_alert_id"],
            "tenant_id": alert_data["tenant_id"],
            "status": alert_data["status"],
        }

    def resolve_ops_alert(self, tenant_id: str, ops_alert_id: str, resolved_at: str) -> bool:
        if not tenant_id or not ops_alert_id or not resolved_at:
            raise ValueError("tenant_id, ops_alert_id, and resolved_at are required")

        return self._repository.resolve_alert(
            tenant_id=tenant_id,
            ops_alert_id=ops_alert_id,
            resolved_at=resolved_at,
        )
