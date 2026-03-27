"""Minimal synchronous in-process internal event bus."""

from __future__ import annotations

from domain.internal_event_contracts import (
    EventPublishResult,
    InternalEvent,
    InternalEventSubscriber,
)


class InProcessInternalEventBus:
    def __init__(self, subscribers: list[InternalEventSubscriber] | None = None) -> None:
        self._subscribers = list(subscribers or [])

    def publish(self, event: InternalEvent) -> EventPublishResult:
        failures = 0
        for subscriber in self._subscribers:
            try:
                subscriber.handle(event)
            except Exception:  # noqa: BLE001 - subscriber failures must be isolated
                failures += 1

        if failures > 0:
            return EventPublishResult(
                success=False,
                message=f"{failures} subscriber(s) failed",
            )
        return EventPublishResult(success=True, message=None)
