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
    - On match, creates one ops alert or dedups against an existing open alert.


### Timestamp validation rules
- `occurred_at` (ingestion) must be valid ISO-8601.
- `created_from` / `created_to` (alert reads) must be valid ISO-8601 when provided.
- `resolved_at` (resolve endpoint) must be valid ISO-8601 when provided.
- Invalid timestamps return `400` with `validation_error`.

### Alerts persistence and lifecycle foundation
- `ops_alerts` are persisted through repository/service layers.
- Read endpoints:
  - `GET /internal/alerts?tenant_id=...`
  - `GET /internal/alerts/{ops_alert_id}?tenant_id=...`
- Resolve endpoint:
  - `POST /internal/alerts/{ops_alert_id}/resolve?tenant_id=...`
  - optional JSON body: `{ "resolved_at": "..." }`
  - if omitted, server-generated UTC timestamp is used.
- Alert list supports:
  - `limit`, `offset`, `status`, `created_after`, `created_before`, `sort_order`
  - `sort_order` accepts `asc` or `desc` (default `desc`)
  - `limit` defaults to `50` and is capped at `200`
- Tenant scoping is mandatory for all alert reads and resolve operations.


### Lifecycle model and transition rules
- Allowed alert statuses are explicit and constrained to:
  - `open`
  - `resolved`
- Arbitrary statuses are rejected by service/repository validation.
- Resolve transition is tenant-scoped and only allows:
  - `open -> resolved`
- Resolving a `resolved` alert is idempotent success (`200`) and does **not**
  overwrite existing lifecycle metadata (`resolved_at`, `resolved_by`).
- Resolving a non-existent alert returns `404`.

### Dedup behavior after resolution
- Dedup only blocks when an **open** alert exists for the dedup key.
- After an alert is resolved, a new alert with the same dedup key can be created.

### Dedup rule currently implemented
For `booking_failure_high_severity` alerts only:
- prevent duplicate **open** alerts when all match:
  - `tenant_id`
  - `alert_type`
  - `source_event_id`
- Detector result contract:
  - `matched_created`
  - `matched_deduped`
  - `no_match`

## Database and migrations
- `db/migrations/0001_create_activity_events.sql`
- `db/migrations/0002_create_ops_alerts.sql`
- `db/migrations/0003_add_ops_alerts_dedup_open_lookup_index.sql`

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
  - domain services and lifecycle behavior
  - detectors and orchestration
  - ingestion/read/resolve HTTP routes
  - config/bootstrap modules

Run:

```bash
python -m unittest discover -s tests -v
```

## Intentionally not implemented yet
- notifications / outbound delivery
- websocket streaming
- dashboard/UI work
- distributed dedup engine / cross-process locking
