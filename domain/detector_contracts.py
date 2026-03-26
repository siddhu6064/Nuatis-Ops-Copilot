"""Detector contracts for orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DetectorResult:
    alert_type: str
    dedup_key: str
    payload: dict[str, Any]
    detector_name: str | None = None
    severity: str | None = None
    metadata: dict[str, Any] | None = None


class Detector(Protocol):
    def evaluate(self, event: dict[str, Any]) -> DetectorResult | None:
        ...
