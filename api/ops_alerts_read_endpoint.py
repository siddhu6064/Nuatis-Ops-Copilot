"""Minimal internal read handlers for ops alerts."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection
from domain.alert_query_params import AlertQueryParams
from domain.ops_alerts_read_service import OpsAlertsReadService
from repositories.ops_alerts_repository import OpsAlertsRepository


def list_ops_alerts(
    tenant_id: str | None,
    db: DatabaseConnection,
    *,
    limit: str | int | None = None,
    offset: str | int | None = None,
    status: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    sort_order: str | None = None,
) -> tuple[int, dict[str, Any]]:
    service = OpsAlertsReadService(OpsAlertsRepository(db))

    try:
        params = AlertQueryParams(
            tenant_id=tenant_id or "",
            status=status,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
            sort_order=sort_order or "desc",
        )
        data = service.list_alerts(params)
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

    return (
        200,
        {
            "success": True,
            "data": data["alerts"],
            "meta": {
                "tenant_id": data["tenant_id"],
                "pagination": data["pagination"],
                "filters": data["filters"],
            },
        },
    )


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


def get_ops_alert_detail(
    tenant_id: str | None, ops_alert_id: str, db: DatabaseConnection
) -> tuple[int, dict[str, Any]]:
    return get_ops_alert(tenant_id=tenant_id, ops_alert_id=ops_alert_id, db=db)
