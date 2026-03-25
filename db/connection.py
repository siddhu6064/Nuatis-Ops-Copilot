"""Database connection bootstrap module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from urllib.parse import urlparse


@dataclass
class DatabaseConnection:
    backend: str
    connection: object


def connect(database_url: str) -> DatabaseConnection:
    parsed = urlparse(database_url)

    if parsed.scheme == "sqlite":
        raw_path = parsed.path or ":memory:"
        if raw_path == "/:memory:":
            sqlite_path = ":memory:"
        else:
            sqlite_path = raw_path.lstrip("/")
            if not sqlite_path:
                sqlite_path = "nuatis_ops.db"
            if sqlite_path != ":memory:":
                Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(sqlite_path)
        return DatabaseConnection(backend="sqlite", connection=conn)

    if parsed.scheme in {"postgres", "postgresql"}:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for postgres connections"
            ) from exc

        conn = psycopg.connect(database_url)
        return DatabaseConnection(backend="postgres", connection=conn)

    raise ValueError(f"Unsupported database scheme: {parsed.scheme}")


def disconnect(db: DatabaseConnection) -> None:
    close = getattr(db.connection, "close", None)
    if callable(close):
        close()
