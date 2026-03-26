"""Service settings resolved from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    service_name: str
    environment: str
    log_level: str
    database_url: str
    notifications_enabled: bool
    webhook_url: str | None


def load_settings() -> Settings:
    notifications_enabled = os.getenv("NOTIFICATIONS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url is not None and webhook_url.strip() == "":
        webhook_url = None

    return Settings(
        service_name=os.getenv("SERVICE_NAME", "nuatis_ops_copilot"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./nuatis_ops.db"),
        notifications_enabled=notifications_enabled,
        webhook_url=webhook_url,
    )
