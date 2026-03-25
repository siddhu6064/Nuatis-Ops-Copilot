"""Minimal ingestion endpoint handler for activity events."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from db.connection import DatabaseConnection
from domain.detector_orchestration_service import DetectorOrchestrationService
from domain.ops_alerts_service import OpsAlertsService
from domain.timestamp_validation import is_valid_iso8601
from repositories.activity_events_repository import ActivityEventsRepository
from repositories.ops_alerts_repository import OpsAlertsRepository


ENDPOINT_PATH = "/internal/events/activity"
REQUIRED_FIELDS = (
    "activity_event_id",
    "tenant_id",
    "event_id",
    "event_type",
    "event_source",
    "occurred_at",
    "payload_json",
)


def ingest_activity_event(payload: dict[str, Any], db: DatabaseConnection) -> tuple[int, dict[str, Any]]:
    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in payload or payload[field] is None
    ]
    if missing:
        return (
            400,
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": f"Missing required fields: {', '.join(missing)}",
                },
            },
        )

    if not is_valid_iso8601(payload["occurred_at"]):
        return (
            400,
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": "occurred_at must be a valid ISO-8601 timestamp.",
                },
            },
        )

    repo = ActivityEventsRepository(db)

    normalized_payload_json = payload["payload_json"]
    if isinstance(normalized_payload_json, (dict, list)):
        normalized_payload_json = json.dumps(normalized_payload_json)

    try:
        repo.create_event(
            {
                "activity_event_id": payload["activity_event_id"],
                "tenant_id": payload["tenant_id"],
                "event_id": payload["event_id"],
                "event_type": payload["event_type"],
                "event_source": payload["event_source"],
                "occurred_at": payload["occurred_at"],
                "payload_json": normalized_payload_json,
                "contact_id": payload.get("contact_id"),
                "correlation_id": payload.get("correlation_id"),
            }
        )
    except sqlite3.IntegrityError as exc:
        error_message = "Duplicate activity event." 
        raw_error = str(exc)
        if "activity_events.activity_event_id" in raw_error:
            error_message = "An event with this activity_event_id already exists."
        elif "activity_events.tenant_id, activity_events.event_id" in raw_error:
            error_message = "An event with the same tenant_id and event_id already exists."

        return (
            409,
            {
                "success": False,
                "error": {
                    "code": "duplicate_event",
                    "message": error_message,
                },
            },
        )

    orchestration = DetectorOrchestrationService(OpsAlertsService(OpsAlertsRepository(db)))
    detector_input = {**payload, "payload_json": normalized_payload_json}
    detector_summary = orchestration.evaluate_event(detector_input)

    return (
        201,
        {
            "success": True,
            "data": {
                "activity_event_id": payload["activity_event_id"],
                "tenant_id": payload["tenant_id"],
                "event_id": payload["event_id"],
                "detector_summary": detector_summary,
            },
        },
    )
