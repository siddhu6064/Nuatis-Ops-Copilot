"""Persistence access for activity_events."""

from __future__ import annotations

from typing import Any
import sqlite3

from db.connection import DatabaseConnection


class ActivityEventsRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._conn = db.connection
        self._conn.row_factory = sqlite3.Row

    def create_event(self, event: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO activity_events (
                activity_event_id,
                tenant_id,
                event_id,
                event_type,
                event_source,
                occurred_at,
                payload_json,
                contact_id,
                correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["activity_event_id"],
                event["tenant_id"],
                event["event_id"],
                event["event_type"],
                event["event_source"],
                event["occurred_at"],
                event["payload_json"],
                event.get("contact_id"),
                event.get("correlation_id"),
            ),
        )
        self._conn.commit()

    def get_event_by_id(self, tenant_id: str, activity_event_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT activity_event_id, tenant_id, event_id, event_type, event_source,
                   occurred_at, payload_json, contact_id, correlation_id, created_at
            FROM activity_events
            WHERE tenant_id = ? AND activity_event_id = ?
            """,
            (tenant_id, activity_event_id),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    def list_events_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT activity_event_id, tenant_id, event_id, event_type, event_source,
                   occurred_at, payload_json, contact_id, correlation_id, created_at
            FROM activity_events
            WHERE tenant_id = ?
            ORDER BY occurred_at DESC, activity_event_id DESC
            """,
            (tenant_id,),
        ).fetchall()

        return [dict(row) for row in rows]
