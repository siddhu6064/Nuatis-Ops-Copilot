"""Minimal HTTP layer exposing activity event ingestion."""

from __future__ import annotations

from io import BytesIO
import json
from typing import Any, Callable
from wsgiref.simple_server import make_server

from api.activity_events_endpoint import ENDPOINT_PATH, ingest_activity_event
from db.connection import DatabaseConnection, connect, disconnect


JsonDict = dict[str, Any]
StartResponse = Callable[[str, list[tuple[str, str]]], None]


def create_app(db: DatabaseConnection) -> Callable[[dict[str, Any], StartResponse], list[bytes]]:
    def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")

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

            response_body = json.dumps(response).encode("utf-8")
            start_response(
                f"{status_code} { _reason_phrase(status_code) }",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(response_body))),
                ],
            )
            return [response_body]

        response = {"success": False, "error": {"code": "not_found", "message": "Route not found."}}
        response_body = json.dumps(response).encode("utf-8")
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body))),
            ],
        )
        return [response_body]

    return app


def run_http_server(database_url: str, host: str = "0.0.0.0", port: int = 8080) -> None:
    db = connect(database_url)
    app = create_app(db)

    try:
        with make_server(host, port, app) as server:
            server.serve_forever()
    finally:
        disconnect(db)


def _reason_phrase(status_code: int) -> str:
    return {
        201: "Created",
        409: "Conflict",
        400: "Bad Request",
    }.get(status_code, "OK")
