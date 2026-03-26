"""Transport-facing subscriber that normalizes internal alert events into stream messages."""

from __future__ import annotations

from typing import Any, Protocol

from domain.internal_event_contracts import InternalEvent


class AlertStreamSink(Protocol):
    def send(self, message: dict[str, Any]) -> None:
        ...


class AlertStreamMessageSubscriber:
    def __init__(self, sink: AlertStreamSink) -> None:
        self._sink = sink

    def handle(self, event: InternalEvent) -> None:
        if event.event_type not in ("alert_created", "alert_resolved"):
            return

        payload = event.payload
        status = payload.get("status")
        if status is None:
            status = "open" if event.event_type == "alert_created" else "resolved"

        message = {
            "event_type": event.event_type,
            "ops_alert_id": payload.get("ops_alert_id"),
            "tenant_id": payload.get("tenant_id"),
            "status": status,
            "alert_type": payload.get("alert_type"),
            "created_at": payload.get("created_at"),
            "resolved_at": payload.get("resolved_at"),
            "resolved_by": payload.get("resolved_by"),
            "details_json": payload.get("details_json"),
        }
        self._sink.send(message)
