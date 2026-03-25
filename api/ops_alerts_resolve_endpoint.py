"""Minimal internal resolve handler for ops alerts."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository


def resolve_ops_alert(
    tenant_id: str | None,
    ops_alert_id: str,
    db: DatabaseConnection,
    *,
    resolved_at: str | None = None,
    resolved_by: str | None = None,
) -> tuple[int, dict[str, Any]]:
    service = OpsAlertsService(OpsAlertsRepository(db))

    try:
        resolved = service.resolve_ops_alert(
            tenant_id=tenant_id or "",
            ops_alert_id=ops_alert_id,
            resolved_at=resolved_at,
            resolved_by=resolved_by,
        )
    except ValueError as exc:
        return (
            400,
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": str(exc),
                },
            },
        )

    if not resolved:
        return (
            404,
            {
                "success": False,
                "error": {
                    "code": "not_found",
                    "message": "Alert not found for tenant.",
                },
            },
        )

    return (200, {"success": True, "data": {"ops_alert_id": ops_alert_id, "status": "resolved"}})
