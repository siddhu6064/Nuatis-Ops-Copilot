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

    def find_open_alert_by_dedup_key(
        self,
        *,
        tenant_id: str,
        alert_type: str,
        source_event_id: str,
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                   alert_type, status, details_json, created_at, resolved_at
            FROM ops_alerts
            WHERE tenant_id = ?
              AND alert_type = ?
              AND source_event_id = ?
              AND status = 'open'
            ORDER BY created_at DESC, ops_alert_id DESC
            LIMIT 1
            """,
            (tenant_id, alert_type, source_event_id),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    def list_alerts_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        alert_type: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            """
            SELECT ops_alert_id, tenant_id, source_activity_event_id, source_event_id,
                   alert_type, status, details_json, created_at, resolved_at
            FROM ops_alerts
            WHERE tenant_id = ?
            """
        )
        params: list[Any] = [tenant_id]

        if status is not None:
            query += " AND status = ?"
            params.append(status)

        if alert_type is not None:
            query += " AND alert_type = ?"
            params.append(alert_type)

        if created_from is not None:
            query += " AND created_at >= ?"
            params.append(created_from)

        if created_to is not None:
            query += " AND created_at <= ?"
            params.append(created_to)

        query += " ORDER BY created_at DESC, ops_alert_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
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
