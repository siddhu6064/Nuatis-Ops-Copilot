"""Outbound notification contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    message: str | None = None


class Notifier(Protocol):
    def notify(self, alert: dict[str, Any]) -> NotificationResult:
        ...
