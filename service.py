"""Nuatis Ops Copilot service bootstrap entry point."""

from __future__ import annotations

from config.env import load_env_file
from config.settings import load_settings
from config.logger import get_logger
from db.connection import connect, disconnect


def start_service() -> int:
    load_env_file()
    settings = load_settings()
    logger = get_logger(settings.service_name, settings.log_level)

    db = connect(settings.database_url)
    logger.info(
        "Service bootstrapped",
        extra={
            "environment": settings.environment,
            "database_backend": db.backend,
        },
    )

    disconnect(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(start_service())
