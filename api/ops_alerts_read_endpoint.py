"""Minimal internal read handlers for ops alerts."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection
from domain.ops_alerts_read_service import OpsAlertsReadService
from repositories.ops_alerts_repository import OpsAlertsRepository


def list_ops_alerts(
    tenant_id: str | None,
    db: DatabaseConnection,
    *,
    limit: str | int | None = None,
    offset: str | int | None = None,
    status: str | None = None,
    alert_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> tuple[int, dict[str, Any]]:
    service = OpsAlertsReadService(OpsAlertsRepository(db))

    try:
        data = service.list_alerts(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            status=status,
            alert_type=alert_type,
            created_from=created_from,
            created_to=created_to,
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

    return (200, {"success": True, "data": data})


def get_ops_alert(tenant_id: str | None, ops_alert_id: str, db: DatabaseConnection) -> tuple[int, dict[str, Any]]:
    service = OpsAlertsReadService(OpsAlertsRepository(db))

    try:
        alert = service.get_alert(tenant_id=tenant_id, ops_alert_id=ops_alert_id)
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

    if alert is None:
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

    return (200, {"success": True, "data": alert})
