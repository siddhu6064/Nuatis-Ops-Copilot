# Nuatis Ops Copilot

Nuatis Ops Copilot is a standalone backend service for operational intelligence.

## What is implemented now

### API response contract
- Success responses use:
  - `{"success": true, "data": ...}`
  - optional `meta` when pagination/count metadata is useful.
- Error responses use:
  - `{"success": false, "error": {"code": "...", "message": "..."}}`
- Common status codes:
  - `200` success
  - `400` validation error
  - `404` not found
  - `409` duplicate ingest conflict
  - `500` unexpected error

### Ingestion
- `POST /internal/events/activity`
- Purpose: persist one activity event and run detector orchestration.
- Request body (required fields):
  - `activity_event_id`, `tenant_id`, `event_id`, `event_type`, `event_source`,
    `occurred_at`, `payload_json`
- Success (`201`):
  - `{"success": true, "data": {"activity_event_id": "...", "tenant_id": "...", "event_id": "...", "detector_summary": {...}}}`
- Error (`400`, `409`):
  - `{"success": false, "error": {"code": "...", "message": "..."}}`

### Detector orchestration
- `DetectorOrchestrationService` runs configured detectors in sequence for a single event.
- Current detector set includes:
  - `BookingFailureHighSeverityDetector`
    - Rule: match `event_type == "booking.failed"` and payload severity `"high"`.
    - On match, creates one ops alert or dedups against an existing open alert.

### Notifications (minimal webhook foundation)
- Notifications are best-effort and synchronous.
- Notifications are attempted only when detector orchestration results in a **newly created** alert.
- Notifications are **not** attempted for:
  - deduped alerts
  - read requests
  - resolve requests
- Webhook payload fields:
  - `ops_alert_id`, `tenant_id`, `status`, `alert_type`, `created_at`, `details_json`
- Failure behavior:
  - notification failure does **not** block alert creation
  - orchestration result includes notification attempt/success metadata for created alerts
- Configuration:
  - `NOTIFICATIONS_ENABLED` (`true`/`false`, default `false`)
  - `WEBHOOK_URL` (required when notifications are enabled)


### Timestamp validation rules
- `occurred_at` (ingestion) must be valid ISO-8601.
- `created_from` / `created_to` (alert reads) must be valid ISO-8601 when provided.
- `resolved_at` (resolve endpoint) must be valid ISO-8601 when provided.
- Invalid timestamps return `400` with `validation_error`.

### Alerts persistence and lifecycle foundation
- `ops_alerts` are persisted through repository/service layers.
- Tenant scoping is mandatory for all alert reads and resolve operations.

### Alert list endpoint
- `GET /internal/alerts?tenant_id=...`
- Purpose: list tenant-scoped alerts with filters and pagination.
- Query params:
  - required: `tenant_id`
  - optional: `status`, `created_after`, `created_before`, `limit`, `offset`, `sort_order`
- Success (`200`):
  - `{"success": true, "data": [ ...alerts... ], "meta": {"tenant_id": "...", "pagination": {"limit": N, "offset": N}, "filters": {...}}}`
- Error (`400`):
  - `{"success": false, "error": {"code": "validation_error", "message": "..."}}`

### Alert detail endpoint
- `GET /internal/alerts/{ops_alert_id}/detail?tenant_id=...`
- Purpose: fetch one tenant-scoped alert record.
- Success (`200`):
  - `{"success": true, "data": {"ops_alert_id": "...", "tenant_id": "...", "status": "...", "created_at": "...", "resolved_at": "...", "resolved_by": "...", "details_json": "..."}}`
- Error (`400`, `404`):
  - `{"success": false, "error": {"code": "...", "message": "..."}}`

### Minimal operator UI (read-only starter)
- `GET /ui/alerts`
- Purpose: tiny in-process HTML page for loading alert lists from existing APIs.
- Uses existing endpoints:
  - `GET /internal/alerts?tenant_id=...`
  - `GET /internal/alerts/{ops_alert_id}/detail?tenant_id=...`
- Current scope:
  - intentionally minimal, read-mostly operator helper page (not a full dashboard)
  - tenant_id input
  - loading/empty/error states
  - status filter (`all`/`open`/`resolved`) using existing list API query parameter
  - manual refresh button
  - table columns: `ops_alert_id`, `status`, `alert_type`, `created_at`
  - optional row click for detail preview
  - minimal resolve action for selected alert using:
    - `POST /internal/alerts/{ops_alert_id}/resolve?tenant_id=...`
    - requires `resolved_by` UI input
    - disabled for already-resolved alerts

### Single resolve endpoint
- `POST /internal/alerts/{ops_alert_id}/resolve?tenant_id=...`
- Purpose: resolve one alert with existing idempotent resolve semantics.
- Optional body: `{ "resolved_at": "...", "resolved_by": "..." }`
- Success (`200`):
  - `{"success": true, "data": {"ops_alert_id": "...", "status": "resolved"}}`
- Error (`400`, `404`):
  - `{"success": false, "error": {"code": "...", "message": "..."}}`

### Bulk resolve endpoint
- `POST /internal/alerts/resolve/bulk`
- Purpose: resolve multiple alerts in one tenant-scoped request.
- Request body:
  - `tenant_id` (required)
  - `ops_alert_ids` non-empty list (required)
  - `resolved_by` (optional), `resolved_at` (optional)
- Success (`200`):
  - `{"success": true, "data": [{"ops_alert_id": "...", "result": "resolved|already_resolved|not_found"}], "meta": {"requested_count": N, "resolved_count": N, "already_resolved_count": N, "not_found_count": N}}`
- Error (`400`):
  - `{"success": false, "error": {"code": "validation_error", "message": "..."}}`


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
- Concurrency hardening (current scope):
  - DB migration `0005_add_ops_alerts_booking_open_dedup_unique_index.sql` adds a unique
    partial index for `booking_failure_high_severity` open alerts on
    `(tenant_id, alert_type, source_event_id)`.
  - This closes the basic check-then-insert race where concurrent writers could otherwise
    both pass pre-insert dedup lookup.
  - Service-level behavior translates an insert uniqueness conflict on this path back into
    a deduped result when an open matching alert is found after conflict.
  - This is a single-database safety improvement only; distributed/global exactly-once
    semantics are intentionally not implemented yet.

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
- `db/migrations/0004_add_resolved_by_to_ops_alerts.sql`
- `db/migrations/0005_add_ops_alerts_booking_open_dedup_unique_index.sql`

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
# Canonical repo-wide test command:
python -m unittest discover -s tests -v
```

Do not use `python -m unittest` by itself in this repository; it may not discover the test suite.

## Intentionally not implemented yet
- robust notification delivery features (retries, backoff, dead-lettering)
- websocket streaming
- dashboard/UI work
- distributed dedup engine / cross-process locking
