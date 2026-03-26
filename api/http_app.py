"""Minimal HTTP layer exposing activity event ingestion."""

from __future__ import annotations

from io import BytesIO
import json
from typing import Any, Callable
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from api.activity_events_endpoint import ENDPOINT_PATH, ingest_activity_event
from api.alerts_ui_page import render_alerts_ui_page
from api.ops_alerts_read_endpoint import get_ops_alert, get_ops_alert_detail, list_ops_alerts
from api.ops_alerts_resolve_endpoint import bulk_resolve_ops_alerts, resolve_ops_alert
from db.connection import DatabaseConnection, connect, disconnect


JsonDict = dict[str, Any]
StartResponse = Callable[[str, list[tuple[str, str]]], None]


def create_app(db: DatabaseConnection) -> Callable[[dict[str, Any], StartResponse], list[bytes]]:
    def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
        try:
            method = environ.get("REQUEST_METHOD", "")
            path = environ.get("PATH_INFO", "")
            query_params = parse_qs(environ.get("QUERY_STRING", ""))

            if method == "POST" and path == ENDPOINT_PATH:
                body_length = int(environ.get("CONTENT_LENGTH") or 0)
                raw_body = environ.get("wsgi.input", BytesIO()).read(body_length)

                try:
                    payload = json.loads(raw_body.decode("utf-8") or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("Payload must be a JSON object")
                except (json.JSONDecodeError, ValueError):
                    status_code = 400
                    response: JsonDict = {
                        "success": False,
                        "error": {
                            "code": "validation_error",
                            "message": "Request body must be a valid JSON object.",
                        },
                    }
                else:
                    status_code, response = ingest_activity_event(payload, db)

                return _json_response(status_code, response, start_response)

            if method == "POST" and path.startswith("/internal/alerts/") and path.endswith("/resolve"):
                tenant_id = query_params.get("tenant_id", [None])[0]
                ops_alert_id = path.split("/internal/alerts/", 1)[1].rsplit("/resolve", 1)[0]

                body_length = int(environ.get("CONTENT_LENGTH") or 0)
                raw_body = environ.get("wsgi.input", BytesIO()).read(body_length)

                resolved_at: str | None = None
                resolved_by: str | None = None
                if raw_body:
                    try:
                        payload = json.loads(raw_body.decode("utf-8"))
                        if not isinstance(payload, dict):
                            raise ValueError("Payload must be a JSON object")
                        resolved_at = payload.get("resolved_at")
                        resolved_by = payload.get("resolved_by")
                    except (json.JSONDecodeError, ValueError):
                        return _json_response(
                            400,
                            {
                                "success": False,
                                "error": {
                                    "code": "validation_error",
                                    "message": "Request body must be a valid JSON object.",
                                },
                            },
                            start_response,
                        )

                status_code, response = resolve_ops_alert(
                    tenant_id,
                    ops_alert_id,
                    db,
                    resolved_at=resolved_at,
                    resolved_by=resolved_by,
                )
                return _json_response(status_code, response, start_response)

            if method == "POST" and path == "/internal/alerts/resolve/bulk":
                body_length = int(environ.get("CONTENT_LENGTH") or 0)
                raw_body = environ.get("wsgi.input", BytesIO()).read(body_length)
                try:
                    payload = json.loads(raw_body.decode("utf-8") or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("Payload must be a JSON object")
                except (json.JSONDecodeError, ValueError):
                    return _json_response(
                        400,
                        {
                            "success": False,
                            "error": {
                                "code": "validation_error",
                                "message": "Request body must be a valid JSON object.",
                            },
                        },
                        start_response,
                    )

                status_code, response = bulk_resolve_ops_alerts(payload, db)
                return _json_response(status_code, response, start_response)

            if method == "GET" and path == "/internal/alerts":
                tenant_id = query_params.get("tenant_id", [None])[0]
                status_code, response = list_ops_alerts(
                    tenant_id,
                    db,
                    limit=query_params.get("limit", [None])[0],
                    offset=query_params.get("offset", [None])[0],
                    status=query_params.get("status", [None])[0],
                    created_after=query_params.get("created_after", [None])[0],
                    created_before=query_params.get("created_before", [None])[0],
                    sort_order=query_params.get("sort_order", [None])[0],
                )
                return _json_response(status_code, response, start_response)

            if method == "GET" and path == "/ui/alerts":
                return _html_response(render_alerts_ui_page(), start_response)

            if method == "GET" and path.startswith("/internal/alerts/") and path.endswith("/detail"):
                tenant_id = query_params.get("tenant_id", [None])[0]
                ops_alert_id = path.split("/internal/alerts/", 1)[1].rsplit("/detail", 1)[0]
                status_code, response = get_ops_alert_detail(tenant_id, ops_alert_id, db)
                return _json_response(status_code, response, start_response)

            if method == "GET" and path.startswith("/internal/alerts/"):
                tenant_id = query_params.get("tenant_id", [None])[0]
                ops_alert_id = path.split("/internal/alerts/", 1)[1]
                status_code, response = get_ops_alert(tenant_id, ops_alert_id, db)
                return _json_response(status_code, response, start_response)

            response = {"success": False, "error": {"code": "not_found", "message": "Route not found."}}
            return _json_response(404, response, start_response)
        except Exception:
            return _json_response(
                500,
                {
                    "success": False,
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred.",
                    },
                },
                start_response,
            )

    return app


def run_http_server(database_url: str, host: str = "0.0.0.0", port: int = 8080) -> None:
    db = connect(database_url)
    app = create_app(db)

    try:
        with make_server(host, port, app) as server:
            server.serve_forever()
    finally:
        disconnect(db)


def _json_response(
    status_code: int, response: JsonDict, start_response: StartResponse
) -> list[bytes]:
    response_body = json.dumps(response).encode("utf-8")
    start_response(
        f"{status_code} {_reason_phrase(status_code)}",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body))),
        ],
    )
    return [response_body]


def _reason_phrase(status_code: int) -> str:
    return {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
        409: "Conflict",
    }.get(status_code, "OK")


def _html_response(html: str, start_response: StartResponse) -> list[bytes]:
    response_body = html.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(response_body))),
        ],
    )
    return [response_body]
