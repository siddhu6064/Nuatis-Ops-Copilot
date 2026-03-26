"""Internal domain event publishing contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


InternalEventType = Literal["alert_created", "alert_resolved"]


@dataclass(frozen=True)
class InternalEvent:
    event_type: InternalEventType
    payload: dict[str, Any]


@dataclass(frozen=True)
class EventPublishResult:
    success: bool
    message: str | None = None


class InternalEventPublisher(Protocol):
    def publish(self, event: InternalEvent) -> EventPublishResult:
        ...
