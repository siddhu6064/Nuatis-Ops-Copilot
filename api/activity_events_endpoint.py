"""Minimal ingestion endpoint handler for activity events."""

from __future__ import annotations

import sqlite3
from typing import Any

from db.connection import DatabaseConnection
from domain.detector_orchestration_service import DetectorOrchestrationService
from domain.ops_alerts_service import OpsAlertsService
from repositories.activity_events_repository import ActivityEventsRepository
from repositories.ops_alerts_repository import OpsAlertsRepository
from workers.detectors.booking_failure_high_severity_detector import (
    BookingFailureHighSeverityDetector,
)


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
    missing = [field for field in REQUIRED_FIELDS if not payload.get(field)]
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

    events_repo = ActivityEventsRepository(db)

    try:
        events_repo.create_event(
            {
                "activity_event_id": payload["activity_event_id"],
                "tenant_id": payload["tenant_id"],
                "event_id": payload["event_id"],
                "event_type": payload["event_type"],
                "event_source": payload["event_source"],
                "occurred_at": payload["occurred_at"],
                "payload_json": payload["payload_json"],
                "contact_id": payload.get("contact_id"),
                "correlation_id": payload.get("correlation_id"),
            }
        )
    except sqlite3.IntegrityError:
        return (
            409,
            {
                "success": False,
                "error": {
                    "code": "duplicate_event",
                    "message": "An event with the same tenant_id and event_id already exists.",
                },
            },
        )

    orchestration = DetectorOrchestrationService(
        BookingFailureHighSeverityDetector(OpsAlertsService(OpsAlertsRepository(db)))
    )
    detector_summary = orchestration.evaluate_event(payload)

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
