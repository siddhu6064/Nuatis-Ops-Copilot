"""Lightweight ISO-8601 timestamp validation helpers."""

from __future__ import annotations

from datetime import datetime


def is_valid_iso8601(value: str) -> bool:
    if not isinstance(value, str):
        return False

    candidate = value.strip()
    if candidate == "":
        return False

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False

    return True
