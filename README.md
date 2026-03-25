# Nuatis Ops Copilot

Nuatis Ops Copilot is a standalone backend service for operational intelligence.

## What is implemented now

### Ingestion
- `POST /internal/events/activity`
- Validates required fields, persists one activity event, then runs detector orchestration.
- Returns a detector summary in the success response.

### Detector orchestration
- `DetectorOrchestrationService` runs configured detectors in sequence for a single event.
- Current detector set includes:
  - `BookingFailureHighSeverityDetector`
    - Rule: match `event_type == "booking.failed"` and payload severity `"high"`.
    - On match, creates one ops alert.

### Alerts persistence and reads
- `ops_alerts` are persisted through repository/service layers.
- Internal read endpoints:
  - `GET /internal/alerts?tenant_id=...`
  - `GET /internal/alerts/{ops_alert_id}?tenant_id=...`
- Alert list supports:
  - `limit`, `offset`, `status`, `alert_type`, `created_from`, `created_to`
- Tenant scoping is mandatory for all alert reads.

## Database and migrations
- `db/migrations/0001_create_activity_events.sql`
- `db/migrations/0002_create_ops_alerts.sql`

Both schemas are tenant-scoped and designed for incremental lifecycle expansion.

## Configuration and bootstrap
- Environment loader: `config/env.py`
- Settings: `config/settings.py`
- Logger: `config/logger.py`
- DB connection: `db/connection.py`
- Service entrypoint: `service.py`

## Tests
- Test suite is under `tests/` and covers:
  - migrations
  - repositories
  - domain services
  - detectors and orchestration
  - ingestion handler and HTTP routes
  - config/bootstrap modules

Run:

```bash
python -m unittest discover -s tests -v
```

## Next planned lifecycle step (not implemented yet)
- Alert resolve/dedup lifecycle hardening:
  - define dedup key strategy (example: `tenant_id + alert_type + source_event_id`)
  - add dedup window/rules at alert creation boundary
  - keep dedup behavior explicit and tenant-scoped
