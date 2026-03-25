# Project Structure

```
.
├── api/
│   ├── activity_events_endpoint.py
│   ├── http_app.py
│   └── ops_alerts_read_endpoint.py
├── config/
│   ├── env.py
│   ├── logger.py
│   └── settings.py
├── db/
│   ├── connection.py
│   ├── migrations/
│   │   ├── 0001_create_activity_events.sql
│   │   └── 0002_create_ops_alerts.sql
│   └── models/
├── domain/
│   ├── detector_orchestration_service.py
│   ├── ops_alerts_read_service.py
│   └── ops_alerts_service.py
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
  - `http_app.py` provides minimal WSGI routing.

- `config/`
  - Environment loading, runtime settings, and logger setup.

- `db/`
  - Connection bootstrap and SQL migrations.

- `domain/`
  - Application services and orchestration logic.
  - Read service (`ops_alerts_read_service.py`) owns alert read validation and filtering behavior.

- `repositories/`
  - Tenant-scoped persistence access for events and alerts.

- `workers/detectors/`
  - Rule evaluation modules (currently one hardcoded detector).

- `tests/`
  - Unit/integration-style module tests for behavior and tenant isolation.
