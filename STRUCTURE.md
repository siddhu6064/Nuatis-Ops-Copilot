# Project Structure

```
.
├── api/
│   ├── activity_events_endpoint.py
│   ├── http_app.py
│   ├── ops_alerts_read_endpoint.py
│   └── ops_alerts_resolve_endpoint.py
├── config/
│   ├── env.py
│   ├── logger.py
│   └── settings.py
├── db/
│   ├── connection.py
│   ├── migrations/
│   │   ├── 0001_create_activity_events.sql
│   │   ├── 0002_create_ops_alerts.sql
│   │   └── 0003_add_ops_alerts_dedup_open_lookup_index.sql
│   └── models/
├── domain/
│   ├── detector_orchestration_service.py
│   ├── ops_alerts_read_service.py
│   ├── ops_alerts_service.py
│   └── timestamp_validation.py
├── repositories/
│   ├── activity_events_repository.py
│   └── ops_alerts_repository.py
├── tests/
├── workers/
│   └── detectors/
│       └── booking_failure_high_severity_detector.py
├── README.md
├── STRUCTURE.md
└── service.py
```

## Responsibilities

- `api/`
  - HTTP-facing handlers and route-level request/response shaping.
  - `http_app.py` provides minimal WSGI routing for ingest/read/resolve.

- `config/`
  - Environment loading, runtime settings, and logger setup.

- `db/`
  - Connection bootstrap and SQL migrations.

- `domain/`
  - Application services, orchestration, and validation helpers.
  - `ops_alerts_read_service.py` handles read validation/filtering.
  - `ops_alerts_service.py` handles create/resolve and dedup-at-create foundation.
  - `timestamp_validation.py` provides lightweight ISO-8601 validation helpers.

- `repositories/`
  - Tenant-scoped persistence access for events and alerts.
  - Explicit query methods for read filters and dedup lookup.

- `workers/detectors/`
  - Rule evaluation modules (currently one hardcoded detector).

- `tests/`
  - Unit/integration-style module tests for behavior and tenant isolation.
