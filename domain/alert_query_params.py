"""Read-path query contract for listing alerts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertQueryParams:
    tenant_id: str
    status: str | None = None
    created_after: str | None = None
    created_before: str | None = None
    limit: str | int | None = 50
    offset: str | int | None = 0
    sort_order: str | None = "desc"
