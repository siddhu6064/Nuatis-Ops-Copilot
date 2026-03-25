"""Minimal internal read handlers for ops alerts."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection
from repositories.ops_alerts_repository import OpsAlertsRepository


def list_ops_alerts(tenant_id: str | None, db: DatabaseConnection) -> tuple[int, dict[str, Any]]:
    if tenant_id is None or tenant_id == "":
        return (
            400,
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": "tenant_id is required.",
                },
            },
        )

    repo = OpsAlertsRepository(db)
    alerts = repo.list_alerts_by_tenant(tenant_id)

    return (
        200,
        {
            "success": True,
            "data": {
                "tenant_id": tenant_id,
                "alerts": alerts,
            },
        },
    )


def get_ops_alert(tenant_id: str | None, ops_alert_id: str, db: DatabaseConnection) -> tuple[int, dict[str, Any]]:
    if tenant_id is None or tenant_id == "":
        return (
            400,
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": "tenant_id is required.",
                },
            },
        )

    repo = OpsAlertsRepository(db)
    alert = repo.get_alert_by_id(tenant_id, ops_alert_id)

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

    return (
        200,
        {
            "success": True,
            "data": alert,
        },
    )
