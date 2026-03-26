"""Minimal webhook notifier with injectable transport."""

from __future__ import annotations

import json
from typing import Any, Protocol
from urllib import request
from urllib.error import URLError

from domain.notification_contracts import NotificationResult


class WebhookTransport(Protocol):
    def send(self, webhook_url: str, payload: dict[str, Any]) -> NotificationResult:
        ...


class WebhookNotifier:
    def __init__(self, webhook_url: str, transport: WebhookTransport) -> None:
        self._webhook_url = webhook_url
        self._transport = transport

    def notify(self, alert: dict[str, Any]) -> NotificationResult:
        payload = {
            "ops_alert_id": alert.get("ops_alert_id"),
            "tenant_id": alert.get("tenant_id"),
            "status": alert.get("status"),
            "alert_type": alert.get("alert_type"),
            "created_at": alert.get("created_at"),
            "details_json": alert.get("details_json"),
        }
        return self._transport.send(self._webhook_url, payload)


class UrllibWebhookTransport:
    def send(self, webhook_url: str, payload: dict[str, Any]) -> NotificationResult:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5):
                return NotificationResult(success=True, message="delivered")
        except URLError:
            return NotificationResult(success=False, message="delivery_failed")


class NoopWebhookTransport:
    def send(self, webhook_url: str, payload: dict[str, Any]) -> NotificationResult:
        return NotificationResult(success=False, message="transport_not_configured")
