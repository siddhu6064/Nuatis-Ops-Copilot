"""Persistence access for ops_alerts."""

from __future__ import annotations

from typing import Any
import sqlite3

from db.connection import DatabaseConnection


class OpsAlertsRepository:
    REQUIRED_CREATE_FIELDS = (
        "ops_alert_id",
        "tenant_id",
        "alert_type",
        "status",
    )

    def __init__(self, db: DatabaseConnection) -> None:
        self._conn = db.connection
        self._conn.row_factory = sqlite3.Row

    def create_alert(self, alert: dict[str, Any]) -> None:
        missing = [field for field in self.REQUIRED_CREATE_FIELDS if not alert.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        self._conn.execute(
            """
            INSERT INTO ops_alerts (
                ops_alert_id,
                tenant_id,
                source_activity_event_id,
                source_event_id,
                alert_type,
                status,
                details_json,
                resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert["ops_alert_id"],
                alert["tenant_id"],
                alert.get("source_activity_event_id"),
                alert.get("source_event_id"),
                alert["alert_type"],
                alert["status"],
                alert.get("details_json"),
                alert.get("resolved_at"),
            ),
        )
        self._conn.commit()

    def get_alert_by_id(self, tenant_id: str, ops_alert_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                   alert_type, status, details_json, created_at, resolved_at
            FROM ops_alerts
            WHERE tenant_id = ? AND ops_alert_id = ?
            """,
            (tenant_id, ops_alert_id),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    def list_alerts_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                   alert_type, status, details_json, created_at, resolved_at
            FROM ops_alerts
            WHERE tenant_id = ?
            ORDER BY created_at DESC, ops_alert_id DESC
            """,
            (tenant_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    def resolve_alert(self, tenant_id: str, ops_alert_id: str, resolved_at: str) -> bool:
        cursor = self._conn.execute(
            """
            UPDATE ops_alerts
            SET status = ?, resolved_at = ?
            WHERE tenant_id = ? AND ops_alert_id = ?
            """,
            ("resolved", resolved_at, tenant_id, ops_alert_id),
        )
        self._conn.commit()

        return cursor.rowcount > 0
