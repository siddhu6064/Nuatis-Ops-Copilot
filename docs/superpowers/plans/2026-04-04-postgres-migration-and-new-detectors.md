# Postgres Migration and New Detectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the SQLite-only DB layer to support Supabase PostgreSQL, add three new alert detectors (LeadStalled, AppointmentNoShow, FollowUpMissed), and document all event payload schemas.

**Architecture:** A thin `_PgAdapter` class in `db/connection.py` normalizes psycopg2 to match the sqlite3 connection interface (converts `?`→`%s` params, provides `dict`-returning cursors), so all repositories work unchanged for both backends. New detectors follow the exact pattern of the existing two. SQLite in-memory remains the test database; no test infra changes needed.

**Tech Stack:** Python stdlib, psycopg2-binary, SQLite (tests), Supabase PostgreSQL (production)

---

## File Map

### Modified files

| File                                                                    | What changes                                                                                                                         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `requirements.txt`                                                      | Add `psycopg2-binary>=2.9`                                                                                                           |
| `db/connection.py`                                                      | Replace `psycopg` import with `psycopg2`; add `_PgAdapter`; set sqlite3 row_factory at connect time; expose `DatabaseIntegrityError` |
| `repositories/ops_alerts_repository.py`                                 | Remove `self._conn.row_factory = sqlite3.Row` (now done in connect()); remove `import sqlite3`; catch `DatabaseIntegrityError`       |
| `repositories/activity_events_repository.py`                            | Remove `self._conn.row_factory = sqlite3.Row`; remove `import sqlite3`                                                               |
| `domain/ops_alerts_service.py`                                          | Add 3 new types to `DEDUP_ALERT_TYPES`; catch `DatabaseIntegrityError` instead of `sqlite3.IntegrityError`                           |
| `domain/detector_orchestration_service.py`                              | Import and register 3 new detectors in `DETECTOR_REGISTRY`                                                                           |
| `db/migrations/0001_create_activity_events.sql`                         | `created_at TEXT` → `created_at TIMESTAMPTZ`                                                                                         |
| `db/migrations/0002_create_ops_alerts.sql`                              | `created_at TEXT` → `created_at TIMESTAMPTZ`                                                                                         |
| `db/migrations/0003_add_ops_alerts_dedup_open_lookup_index.sql`         | No change (already Postgres-compatible)                                                                                              |
| `db/migrations/0004_add_resolved_by_to_ops_alerts.sql`                  | No change (already Postgres-compatible)                                                                                              |
| `db/migrations/0005_add_ops_alerts_booking_open_dedup_unique_index.sql` | No change (already Postgres-compatible)                                                                                              |
| `db/migrations/0006_add_ops_alerts_call_open_dedup_unique_index.sql`    | No change (already Postgres-compatible)                                                                                              |
| `tests/test_detector_orchestration_service.py`                          | Update 3 assertions from `detectors_run == 2` to `detectors_run == 5`                                                                |
| `.env.example`                                                          | Change `DATABASE_URL` to show `postgres://` format                                                                                   |

### New files

| File                                                                                | Purpose                                                          |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `db/migrations/0007_add_ops_alerts_lead_stalled_open_dedup_unique_index.sql`        | Partial unique index for lead_stalled_high_severity dedup        |
| `db/migrations/0008_add_ops_alerts_appointment_no_show_open_dedup_unique_index.sql` | Partial unique index for appointment_no_show_high_severity dedup |
| `db/migrations/0009_add_ops_alerts_follow_up_missed_open_dedup_unique_index.sql`    | Partial unique index for follow_up_missed_high_severity dedup    |
| `workers/detectors/lead_stalled_detector.py`                                        | LeadStalledDetector implementation                               |
| `workers/detectors/appointment_no_show_detector.py`                                 | AppointmentNoShowDetector implementation                         |
| `workers/detectors/follow_up_missed_detector.py`                                    | FollowUpMissedDetector implementation                            |
| `tests/test_lead_stalled_detector.py`                                               | Full test coverage for LeadStalledDetector                       |
| `tests/test_appointment_no_show_detector.py`                                        | Full test coverage for AppointmentNoShowDetector                 |
| `tests/test_follow_up_missed_detector.py`                                           | Full test coverage for FollowUpMissedDetector                    |
| `docs/event_payload_schemas.md`                                                     | Payload schema docs for all 5 event types                        |

---

## Task 1: psycopg2 dependency + DB connection adapter

**Files:**

- Modify: `requirements.txt`
- Modify: `db/connection.py`

**Context:** `db/connection.py` already has a Postgres branch but imports `psycopg` (v3). The task requires `psycopg2`. The two repositories call `self._conn.execute(sql, params)` with SQLite-style `?` placeholders and set `self._conn.row_factory = sqlite3.Row` in their `__init__`. psycopg2 connections have no `execute()` method and no `row_factory`. A `_PgAdapter` wrapper normalizes the interface so repositories need zero changes for query logic. We also expose a `DatabaseIntegrityError` so the service layer can catch it without importing sqlite3 or psycopg2 directly.

- [ ] **Step 1.1: Add psycopg2-binary to requirements.txt**

Open `requirements.txt` and replace its content:

```text
psycopg2-binary>=2.9
```

- [ ] **Step 1.2: Rewrite db/connection.py**

Replace the full file content:

```python
"""Database connection bootstrap module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from urllib.parse import urlparse
from typing import Any


class DatabaseIntegrityError(Exception):
    """Raised when a unique/integrity constraint is violated, regardless of backend."""


@dataclass
class DatabaseConnection:
    backend: str
    connection: object


class _PgAdapter:
    """Wraps a psycopg2 connection to look like a sqlite3 connection to repositories.

    Responsibilities:
    - Converts ``?`` parameter placeholders to ``%s`` (psycopg2 style).
    - Returns rows as dicts via RealDictCursor so ``dict(row)`` works.
    - Re-raises psycopg2.IntegrityError as DatabaseIntegrityError.
    - Provides executescript() for running multi-statement migration scripts.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()) -> Any:
        import psycopg2.extras  # type: ignore
        import psycopg2  # type: ignore

        pg_sql = sql.replace("?", "%s")
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(pg_sql, params)
        except psycopg2.IntegrityError as exc:
            self._conn.rollback()
            raise DatabaseIntegrityError(str(exc)) from exc
        return cur

    def executescript(self, script: str) -> None:
        """Execute a semicolon-delimited SQL script (used by migration runners)."""
        import psycopg2  # type: ignore

        cur = self._conn.cursor()
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except psycopg2.IntegrityError as exc:
                    self._conn.rollback()
                    raise DatabaseIntegrityError(str(exc)) from exc
        self._conn.commit()

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @property
    def rowcount(self) -> int:
        # Not typically called directly on the adapter; cursors expose this.
        return -1


def connect(database_url: str) -> DatabaseConnection:
    parsed = urlparse(database_url)

    if parsed.scheme == "sqlite":
        raw_path = parsed.path or ":memory:"
        if raw_path == "/:memory:":
            sqlite_path = ":memory:"
        else:
            sqlite_path = raw_path.lstrip("/")
            if not sqlite_path:
                sqlite_path = "nuatis_ops.db"
            if sqlite_path != ":memory:":
                Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row  # set here so repositories don't need to
        return DatabaseConnection(backend="sqlite", connection=conn)

    if parsed.scheme in {"postgres", "postgresql"}:
        try:
            import psycopg2  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2-binary is required for postgres connections: pip install psycopg2-binary"
            ) from exc

        raw_conn = psycopg2.connect(database_url)
        raw_conn.autocommit = False
        return DatabaseConnection(backend="postgres", connection=_PgAdapter(raw_conn))

    raise ValueError(f"Unsupported database scheme: {parsed.scheme}")


def disconnect(db: DatabaseConnection) -> None:
    close = getattr(db.connection, "close", None)
    if callable(close):
        close()
```

- [ ] **Step 1.3: Run existing tests to verify SQLite path still works**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest discover -s tests -v 2>&1 | tail -20
```

Expected: all tests PASS (no errors from the connection change yet — repositories still have `row_factory` assignments, but sqlite3 connection already has it set, so setting it again is harmless).

- [ ] **Step 1.4: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add requirements.txt db/connection.py && git commit -m "feat: add psycopg2 support with _PgAdapter normalizing interface for repositories"
```

---

## Task 2: Remove sqlite3.Row from repositories + update IntegrityError handling

**Files:**

- Modify: `repositories/ops_alerts_repository.py`
- Modify: `repositories/activity_events_repository.py`
- Modify: `domain/ops_alerts_service.py`

**Context:** Both repositories set `self._conn.row_factory = sqlite3.Row` in `__init__`. Since `connect()` now sets it for SQLite, this line is redundant for SQLite. For Postgres (using `_PgAdapter`), this line would silently fail or throw `AttributeError` because `_PgAdapter` has no `row_factory` attribute. Also, `ops_alerts_service.py` catches `sqlite3.IntegrityError` for dedup conflict handling — this needs to catch `DatabaseIntegrityError` instead.

- [ ] **Step 2.1: Update ops_alerts_repository.py**

Replace the `__init__` method. The full updated `__init__` is:

```python
def __init__(self, db: DatabaseConnection) -> None:
    self._conn = db.connection
```

Remove the line `import sqlite3` at the top (it is no longer used by the repository). The full file header becomes:

```python
"""Persistence access for ops_alerts."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection
```

- [ ] **Step 2.2: Update activity_events_repository.py**

Same change — remove `import sqlite3` and simplify `__init__`:

```python
"""Persistence access for activity_events."""

from __future__ import annotations

from typing import Any

from db.connection import DatabaseConnection


class ActivityEventsRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._conn = db.connection
```

(leave all other methods exactly as-is)

- [ ] **Step 2.3: Update ops_alerts_service.py — fix IntegrityError catch**

In `ops_alerts_service.py`, find:

```python
import sqlite3
```

Replace with:

```python
from db.connection import DatabaseIntegrityError
```

Then find the except clause:

```python
        except sqlite3.IntegrityError:
```

Replace with:

```python
        except DatabaseIntegrityError:
```

- [ ] **Step 2.4: Update ops_alerts_service.py — add new DEDUP_ALERT_TYPES**

Find:

```python
    DEDUP_ALERT_TYPES = ("booking_failure_high_severity", "call_failure_high_severity")
```

Replace with:

```python
    DEDUP_ALERT_TYPES = (
        "booking_failure_high_severity",
        "call_failure_high_severity",
        "lead_stalled_high_severity",
        "appointment_no_show_high_severity",
        "follow_up_missed_high_severity",
    )
```

- [ ] **Step 2.5: Run tests**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest discover -s tests -v 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 2.6: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add repositories/ops_alerts_repository.py repositories/activity_events_repository.py domain/ops_alerts_service.py && git commit -m "refactor: remove sqlite3.Row from repos (set at connect time), catch DatabaseIntegrityError, expand DEDUP_ALERT_TYPES"
```

---

## Task 3: Fix migration files 0001-0002 for Postgres compatibility

**Files:**

- Modify: `db/migrations/0001_create_activity_events.sql`
- Modify: `db/migrations/0002_create_ops_alerts.sql`

**Context:** `TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP` fails in PostgreSQL because there is no implicit cast from `timestamptz` to `text`. Changing to `TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP` is valid in both Postgres (native timestamptz column) and SQLite (SQLite ignores the declared type and stores the value as text regardless — `DEFAULT CURRENT_TIMESTAMP` in SQLite always stores an ISO-8601 text string). Migrations 0003–0006 use only `CREATE INDEX IF NOT EXISTS` with `WHERE` partial clauses and `ALTER TABLE ADD COLUMN TEXT` — all of which are valid Postgres syntax. They need no changes.

- [ ] **Step 3.1: Rewrite 0001_create_activity_events.sql**

```sql
CREATE TABLE IF NOT EXISTS activity_events (
    activity_event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    contact_id TEXT,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_events_tenant_id
    ON activity_events (tenant_id);

CREATE INDEX IF NOT EXISTS idx_activity_events_event_type
    ON activity_events (event_type);

CREATE INDEX IF NOT EXISTS idx_activity_events_occurred_at
    ON activity_events (occurred_at);
```

- [ ] **Step 3.2: Rewrite 0002_create_ops_alerts.sql**

```sql
CREATE TABLE IF NOT EXISTS ops_alerts (
    ops_alert_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_activity_event_id TEXT,
    source_event_id TEXT,
    alert_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ops_alerts_tenant_id
    ON ops_alerts (tenant_id);

CREATE INDEX IF NOT EXISTS idx_ops_alerts_status
    ON ops_alerts (status);

CREATE INDEX IF NOT EXISTS idx_ops_alerts_alert_type
    ON ops_alerts (alert_type);

CREATE INDEX IF NOT EXISTS idx_ops_alerts_source_activity_event_id
    ON ops_alerts (source_activity_event_id);
```

- [ ] **Step 3.3: Run tests**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest discover -s tests -v 2>&1 | tail -20
```

Expected: all tests PASS. (SQLite treats TIMESTAMPTZ as NUMERIC affinity and stores timestamps as text strings — no behavioral change for existing tests.)

- [ ] **Step 3.4: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add db/migrations/0001_create_activity_events.sql db/migrations/0002_create_ops_alerts.sql && git commit -m "fix: change created_at to TIMESTAMPTZ for Postgres compatibility in migrations 0001-0002"
```

---

## Task 4: Add migration 0007 + implement LeadStalledDetector (TDD)

**Files:**

- Create: `db/migrations/0007_add_ops_alerts_lead_stalled_open_dedup_unique_index.sql`
- Create: `tests/test_lead_stalled_detector.py`
- Create: `workers/detectors/lead_stalled_detector.py`

**Context:** The detector matches `event_type == "lead.stalled"` with `payload.severity == "high"` AND `payload.days_stalled >= 3`. The dedup key is `source_event_id` from payload (or `event_id` as fallback). The partial unique index mirrors the pattern of 0005 and 0006.

For dedup tests: the test instantiates a full stack (sqlite in-memory, OpsAlertsService, OpsAlertsRepository) just like `test_booking_failure_high_severity_detector.py`. Wait — looking at the existing detector tests, they only test the detector's `evaluate()` method in isolation; they do NOT test full dedup through the service. The dedup integration is covered by `test_detector_orchestration_service.py`. So follow the same pattern: test only the detector's evaluate() method.

- [ ] **Step 4.1: Create migration 0007**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_lead_stalled_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'lead_stalled_high_severity'
      AND source_event_id IS NOT NULL;
```

- [ ] **Step 4.2: Write the failing test file**

Create `tests/test_lead_stalled_detector.py`:

```python
import unittest

from workers.detectors.lead_stalled_detector import LeadStalledDetector


class LeadStalledDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LeadStalledDetector()

    def _base_event(self, **overrides) -> dict:
        event = {
            "activity_event_id": "act_ls_1",
            "tenant_id": "tenant_a",
            "event_id": "evt_ls_1",
            "event_type": "lead.stalled",
            "payload_json": '{"severity":"high","days_stalled":3}',
        }
        event.update(overrides)
        return event

    # --- no_match: wrong event_type ---

    def test_no_match_wrong_event_type(self) -> None:
        result = self.detector.evaluate(
            self._base_event(event_type="booking.failed")
        )
        self.assertIsNone(result)

    # --- no_match: severity not high ---

    def test_no_match_severity_not_high(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"low","days_stalled":5}')
        )
        self.assertIsNone(result)

    def test_no_match_severity_missing(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"days_stalled":5}')
        )
        self.assertIsNone(result)

    # --- no_match: days_stalled below threshold ---

    def test_no_match_days_stalled_too_low(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":2}')
        )
        self.assertIsNone(result)

    def test_no_match_days_stalled_zero(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":0}')
        )
        self.assertIsNone(result)

    # --- matched: correct event ---

    def test_matched_created_returns_detector_result(self) -> None:
        result = self.detector.evaluate(self._base_event())
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "lead_stalled_high_severity")
        self.assertEqual(result.dedup_key, "evt_ls_1")
        self.assertEqual(result.detector_name, "lead_stalled_high_severity")
        self.assertEqual(result.severity, "high")

    def test_matched_at_boundary_days_stalled_equals_3(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":3}')
        )
        self.assertIsNotNone(result)

    def test_matched_high_days_stalled(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"high","days_stalled":30}')
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "lead_stalled_high_severity")

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        result = self.detector.evaluate(
            self._base_event(
                payload_json='{"severity":"high","days_stalled":5,"source_event_id":"src_ls_99"}'
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dedup_key, "src_ls_99")

    # --- dedup: duplicate open alert (via evaluate only — integration dedup tested in orchestration) ---

    def test_evaluate_is_idempotent_same_event_returns_same_result(self) -> None:
        """evaluate() has no side effects; calling it twice returns the same result."""
        event = self._base_event()
        first = self.detector.evaluate(event)
        second = self.detector.evaluate(event)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.alert_type, second.alert_type)
        self.assertEqual(first.dedup_key, second.dedup_key)

    # --- error: missing required fields ---

    def test_required_input_handling_raises_on_missing_event_id(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_ls_err",
                    "tenant_id": "tenant_a",
                    "event_type": "lead.stalled",
                    "payload_json": '{"severity":"high","days_stalled":3}',
                    # missing event_id
                }
            )
```

- [ ] **Step 4.3: Run test to verify it fails (file not created yet)**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_lead_stalled_detector -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'workers.detectors.lead_stalled_detector'`

- [ ] **Step 4.4: Implement LeadStalledDetector**

Create `workers/detectors/lead_stalled_detector.py`:

```python
"""Detector rule for high-severity stalled leads."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import DetectorResult


class LeadStalledDetector:
    """Returns a detector result for high-severity stalled leads (days_stalled >= 3)."""

    def evaluate(self, activity_event: dict[str, Any]) -> DetectorResult | None:
        required = ("activity_event_id", "tenant_id", "event_id", "event_type", "payload_json")
        missing = [field for field in required if not activity_event.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        payload_data = self._normalize_payload(activity_event["payload_json"])

        days_stalled = payload_data.get("days_stalled")
        is_match = (
            activity_event["event_type"] == "lead.stalled"
            and payload_data.get("severity") == "high"
            and isinstance(days_stalled, (int, float))
            and days_stalled >= 3
        )

        if not is_match:
            return None

        source_event_id = str(payload_data.get("source_event_id") or activity_event["event_id"])
        severity = str(payload_data.get("severity"))

        return DetectorResult(
            alert_type="lead_stalled_high_severity",
            dedup_key=source_event_id,
            detector_name="lead_stalled_high_severity",
            payload={
                "rule": "lead.stalled + severity=high + days_stalled>=3",
                "event_type": activity_event["event_type"],
            },
            severity=severity,
            metadata={
                "source_event_id": source_event_id,
                "payload_json": payload_data,
            },
        )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}

        return {}
```

- [ ] **Step 4.5: Run tests to verify they pass**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_lead_stalled_detector -v 2>&1
```

Expected: all tests PASS.

- [ ] **Step 4.6: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add db/migrations/0007_add_ops_alerts_lead_stalled_open_dedup_unique_index.sql workers/detectors/lead_stalled_detector.py tests/test_lead_stalled_detector.py && git commit -m "feat: add LeadStalledDetector with migration 0007 and full test coverage"
```

---

## Task 5: Add migration 0008 + implement AppointmentNoShowDetector (TDD)

**Files:**

- Create: `db/migrations/0008_add_ops_alerts_appointment_no_show_open_dedup_unique_index.sql`
- Create: `tests/test_appointment_no_show_detector.py`
- Create: `workers/detectors/appointment_no_show_detector.py`

**Context:** Matches `event_type == "appointment.no_show"` with `payload.severity == "high"`. No `days_stalled` field. Same dedup key pattern.

- [ ] **Step 5.1: Create migration 0008**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_appointment_no_show_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'appointment_no_show_high_severity'
      AND source_event_id IS NOT NULL;
```

- [ ] **Step 5.2: Write the failing test file**

Create `tests/test_appointment_no_show_detector.py`:

```python
import unittest

from workers.detectors.appointment_no_show_detector import AppointmentNoShowDetector


class AppointmentNoShowDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = AppointmentNoShowDetector()

    def _base_event(self, **overrides) -> dict:
        event = {
            "activity_event_id": "act_ans_1",
            "tenant_id": "tenant_a",
            "event_id": "evt_ans_1",
            "event_type": "appointment.no_show",
            "payload_json": '{"severity":"high"}',
        }
        event.update(overrides)
        return event

    # --- no_match: wrong event_type ---

    def test_no_match_wrong_event_type(self) -> None:
        result = self.detector.evaluate(
            self._base_event(event_type="call.failed")
        )
        self.assertIsNone(result)

    # --- no_match: severity not high ---

    def test_no_match_severity_not_high(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"medium"}')
        )
        self.assertIsNone(result)

    def test_no_match_severity_missing(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"reason":"client_cancelled"}')
        )
        self.assertIsNone(result)

    # --- matched: correct event ---

    def test_matched_created_returns_detector_result(self) -> None:
        result = self.detector.evaluate(self._base_event())
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "appointment_no_show_high_severity")
        self.assertEqual(result.dedup_key, "evt_ans_1")
        self.assertEqual(result.detector_name, "appointment_no_show_high_severity")
        self.assertEqual(result.severity, "high")

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        result = self.detector.evaluate(
            self._base_event(
                payload_json='{"severity":"high","source_event_id":"src_ans_99"}'
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dedup_key, "src_ans_99")

    # --- dedup: idempotent evaluate ---

    def test_evaluate_is_idempotent_same_event_returns_same_result(self) -> None:
        event = self._base_event()
        first = self.detector.evaluate(event)
        second = self.detector.evaluate(event)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.alert_type, second.alert_type)
        self.assertEqual(first.dedup_key, second.dedup_key)

    # --- matched created again after resolve (dedup clears on resolution) ---
    # Note: resolution/dedup clearing is tested at the service/orchestration layer.
    # Here we verify evaluate() produces a result regardless of prior state
    # (the detector is stateless — it only inspects the event payload).

    def test_matched_created_again_evaluate_is_stateless(self) -> None:
        """Detector has no memory; same payload always returns a result."""
        event = self._base_event()
        for _ in range(3):
            result = self.detector.evaluate(event)
            self.assertIsNotNone(result)
            self.assertEqual(result.alert_type, "appointment_no_show_high_severity")

    # --- error: missing required fields ---

    def test_required_input_handling_raises_on_missing_event_id(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_ans_err",
                    "tenant_id": "tenant_a",
                    "event_type": "appointment.no_show",
                    "payload_json": '{"severity":"high"}',
                    # missing event_id
                }
            )
```

- [ ] **Step 5.3: Run test to verify it fails**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_appointment_no_show_detector -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'workers.detectors.appointment_no_show_detector'`

- [ ] **Step 5.4: Implement AppointmentNoShowDetector**

Create `workers/detectors/appointment_no_show_detector.py`:

```python
"""Detector rule for high-severity appointment no-shows."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import DetectorResult


class AppointmentNoShowDetector:
    """Returns a detector result for high-severity appointment no-shows."""

    def evaluate(self, activity_event: dict[str, Any]) -> DetectorResult | None:
        required = ("activity_event_id", "tenant_id", "event_id", "event_type", "payload_json")
        missing = [field for field in required if not activity_event.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        payload_data = self._normalize_payload(activity_event["payload_json"])

        is_match = (
            activity_event["event_type"] == "appointment.no_show"
            and payload_data.get("severity") == "high"
        )

        if not is_match:
            return None

        source_event_id = str(payload_data.get("source_event_id") or activity_event["event_id"])
        severity = str(payload_data.get("severity"))

        return DetectorResult(
            alert_type="appointment_no_show_high_severity",
            dedup_key=source_event_id,
            detector_name="appointment_no_show_high_severity",
            payload={
                "rule": "appointment.no_show + severity=high",
                "event_type": activity_event["event_type"],
            },
            severity=severity,
            metadata={
                "source_event_id": source_event_id,
                "payload_json": payload_data,
            },
        )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}

        return {}
```

- [ ] **Step 5.5: Run tests to verify they pass**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_appointment_no_show_detector -v 2>&1
```

Expected: all tests PASS.

- [ ] **Step 5.6: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add db/migrations/0008_add_ops_alerts_appointment_no_show_open_dedup_unique_index.sql workers/detectors/appointment_no_show_detector.py tests/test_appointment_no_show_detector.py && git commit -m "feat: add AppointmentNoShowDetector with migration 0008 and full test coverage"
```

---

## Task 6: Add migration 0009 + implement FollowUpMissedDetector (TDD)

**Files:**

- Create: `db/migrations/0009_add_ops_alerts_follow_up_missed_open_dedup_unique_index.sql`
- Create: `tests/test_follow_up_missed_detector.py`
- Create: `workers/detectors/follow_up_missed_detector.py`

**Context:** Matches `event_type == "follow_up.missed"` with `payload.severity == "high"`. Same pattern as AppointmentNoShowDetector but different event_type and alert_type.

- [ ] **Step 6.1: Create migration 0009**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_follow_up_missed_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'follow_up_missed_high_severity'
      AND source_event_id IS NOT NULL;
```

- [ ] **Step 6.2: Write the failing test file**

Create `tests/test_follow_up_missed_detector.py`:

```python
import unittest

from workers.detectors.follow_up_missed_detector import FollowUpMissedDetector


class FollowUpMissedDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = FollowUpMissedDetector()

    def _base_event(self, **overrides) -> dict:
        event = {
            "activity_event_id": "act_fum_1",
            "tenant_id": "tenant_a",
            "event_id": "evt_fum_1",
            "event_type": "follow_up.missed",
            "payload_json": '{"severity":"high"}',
        }
        event.update(overrides)
        return event

    # --- no_match: wrong event_type ---

    def test_no_match_wrong_event_type(self) -> None:
        result = self.detector.evaluate(
            self._base_event(event_type="lead.stalled")
        )
        self.assertIsNone(result)

    # --- no_match: severity not high ---

    def test_no_match_severity_not_high(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"severity":"low"}')
        )
        self.assertIsNone(result)

    def test_no_match_severity_missing(self) -> None:
        result = self.detector.evaluate(
            self._base_event(payload_json='{"contact_id":"c123"}')
        )
        self.assertIsNone(result)

    # --- matched: correct event ---

    def test_matched_created_returns_detector_result(self) -> None:
        result = self.detector.evaluate(self._base_event())
        self.assertIsNotNone(result)
        self.assertEqual(result.alert_type, "follow_up_missed_high_severity")
        self.assertEqual(result.dedup_key, "evt_fum_1")
        self.assertEqual(result.detector_name, "follow_up_missed_high_severity")
        self.assertEqual(result.severity, "high")

    def test_dedup_key_prefers_payload_source_event_id_when_present(self) -> None:
        result = self.detector.evaluate(
            self._base_event(
                payload_json='{"severity":"high","source_event_id":"src_fum_42"}'
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dedup_key, "src_fum_42")

    # --- dedup: idempotent evaluate ---

    def test_evaluate_is_idempotent_same_event_returns_same_result(self) -> None:
        event = self._base_event()
        first = self.detector.evaluate(event)
        second = self.detector.evaluate(event)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.alert_type, second.alert_type)
        self.assertEqual(first.dedup_key, second.dedup_key)

    # --- matched created again after resolve ---

    def test_matched_created_again_evaluate_is_stateless(self) -> None:
        """Detector has no memory; same payload always returns a result."""
        event = self._base_event()
        for _ in range(3):
            result = self.detector.evaluate(event)
            self.assertIsNotNone(result)
            self.assertEqual(result.alert_type, "follow_up_missed_high_severity")

    # --- error: missing required fields ---

    def test_required_input_handling_raises_on_missing_event_id(self) -> None:
        with self.assertRaises(ValueError):
            self.detector.evaluate(
                {
                    "activity_event_id": "act_fum_err",
                    "tenant_id": "tenant_a",
                    "event_type": "follow_up.missed",
                    "payload_json": '{"severity":"high"}',
                    # missing event_id
                }
            )
```

- [ ] **Step 6.3: Run test to verify it fails**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_follow_up_missed_detector -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'workers.detectors.follow_up_missed_detector'`

- [ ] **Step 6.4: Implement FollowUpMissedDetector**

Create `workers/detectors/follow_up_missed_detector.py`:

```python
"""Detector rule for high-severity missed follow-ups."""

from __future__ import annotations

import json
from typing import Any

from domain.detector_contracts import DetectorResult


class FollowUpMissedDetector:
    """Returns a detector result for high-severity missed follow-ups."""

    def evaluate(self, activity_event: dict[str, Any]) -> DetectorResult | None:
        required = ("activity_event_id", "tenant_id", "event_id", "event_type", "payload_json")
        missing = [field for field in required if not activity_event.get(field)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        payload_data = self._normalize_payload(activity_event["payload_json"])

        is_match = (
            activity_event["event_type"] == "follow_up.missed"
            and payload_data.get("severity") == "high"
        )

        if not is_match:
            return None

        source_event_id = str(payload_data.get("source_event_id") or activity_event["event_id"])
        severity = str(payload_data.get("severity"))

        return DetectorResult(
            alert_type="follow_up_missed_high_severity",
            dedup_key=source_event_id,
            detector_name="follow_up_missed_high_severity",
            payload={
                "rule": "follow_up.missed + severity=high",
                "event_type": activity_event["event_type"],
            },
            severity=severity,
            metadata={
                "source_event_id": source_event_id,
                "payload_json": payload_data,
            },
        )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}

        return {}
```

- [ ] **Step 6.5: Run tests to verify they pass**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest tests.test_follow_up_missed_detector -v 2>&1
```

Expected: all tests PASS.

- [ ] **Step 6.6: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add db/migrations/0009_add_ops_alerts_follow_up_missed_open_dedup_unique_index.sql workers/detectors/follow_up_missed_detector.py tests/test_follow_up_missed_detector.py && git commit -m "feat: add FollowUpMissedDetector with migration 0009 and full test coverage"
```

---

## Task 7: Register new detectors in DetectorOrchestrationService + fix orchestration tests

**Files:**

- Modify: `domain/detector_orchestration_service.py`
- Modify: `tests/test_detector_orchestration_service.py`

**Context:** Adding 3 detectors to `DETECTOR_REGISTRY` increases `detectors_run` from 2 to 5. Three existing tests assert `detectors_run == 2` — these need updating to `== 5`. The `results` array positions for `booking_failure_high_severity` (index 0) and `call_failure_high_severity` (index 1) are unchanged, so tests checking `results[0]` and `results[1]` are unaffected.

- [ ] **Step 7.1: Update detector_orchestration_service.py**

Replace the import block and `DETECTOR_REGISTRY` at the top of `domain/detector_orchestration_service.py`:

```python
from domain.detector_contracts import Detector
from domain.notification_contracts import Notifier
from domain.ops_alerts_service import OpsAlertsService
from workers.detectors.booking_failure_high_severity_detector import BookingFailureHighSeverityDetector
from workers.detectors.call_failure_high_severity_detector import CallFailureHighSeverityDetector
from workers.detectors.lead_stalled_detector import LeadStalledDetector
from workers.detectors.appointment_no_show_detector import AppointmentNoShowDetector
from workers.detectors.follow_up_missed_detector import FollowUpMissedDetector


DETECTOR_REGISTRY: list[tuple[str, Detector]] = [
    ("booking_failure_high_severity", BookingFailureHighSeverityDetector()),
    ("call_failure_high_severity", CallFailureHighSeverityDetector()),
    ("lead_stalled_high_severity", LeadStalledDetector()),
    ("appointment_no_show_high_severity", AppointmentNoShowDetector()),
    ("follow_up_missed_high_severity", FollowUpMissedDetector()),
]
```

- [ ] **Step 7.2: Update detectors_run assertions in test_detector_orchestration_service.py**

In `tests/test_detector_orchestration_service.py`, the following three tests assert `detectors_run == 2`. Change each to `== 5`:

**test_matching_event_produces_one_match_and_one_alert** (line ~39):

```python
        self.assertEqual(summary["detectors_run"], 5)
```

**test_non_matching_event_produces_zero_matches** (line ~64):

```python
        self.assertEqual(summary["detectors_run"], 5)
```

**test_orchestration_with_both_detectors_only_call_detector_creates_alert** (line ~192):

```python
        self.assertEqual(summary["detectors_run"], 5)
```

- [ ] **Step 7.3: Run all tests**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest discover -s tests -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 7.4: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add domain/detector_orchestration_service.py tests/test_detector_orchestration_service.py && git commit -m "feat: register LeadStalled, AppointmentNoShow, FollowUpMissed detectors in DETECTOR_REGISTRY"
```

---

## Task 8: Write docs/event_payload_schemas.md

**Files:**

- Create: `docs/event_payload_schemas.md`

**Context:** This is pure documentation. Derive the schemas from the detector implementations. `booking.failed` and `call.failed` use `severity` only. `lead.stalled` adds `days_stalled`. All support optional `source_event_id` for custom dedup keys.

- [ ] **Step 8.1: Create docs/event_payload_schemas.md**

````markdown
# Event Payload Schemas

This document describes the expected `payload_json` structure for each event type processed by the Nuatis Ops Copilot alerting service.

---

## booking.failed

**Alert type generated:** `booking_failure_high_severity`

**Required fields:**

| Field      | Type     | Description                          |
| ---------- | -------- | ------------------------------------ |
| `severity` | `string` | Must be `"high"` to trigger an alert |

**Optional fields:**

| Field             | Type     | Description                                                           |
| ----------------- | -------- | --------------------------------------------------------------------- |
| `source_event_id` | `string` | Custom dedup key; falls back to `event_id` if absent                  |
| `reason`          | `string` | Human-readable reason for the failure (e.g. `"provider_unavailable"`) |

**Example JSON:**

```json
{
  "severity": "high",
  "reason": "provider_unavailable",
  "source_event_id": "booking_evt_abc123"
}
```
````

---

## call.failed

**Alert type generated:** `call_failure_high_severity`

**Required fields:**

| Field      | Type     | Description                          |
| ---------- | -------- | ------------------------------------ |
| `severity` | `string` | Must be `"high"` to trigger an alert |

**Optional fields:**

| Field             | Type     | Description                                          |
| ----------------- | -------- | ---------------------------------------------------- |
| `source_event_id` | `string` | Custom dedup key; falls back to `event_id` if absent |
| `provider`        | `string` | Telephony provider name (e.g. `"twilio"`)            |
| `error_code`      | `string` | Provider-specific error code                         |

**Example JSON:**

```json
{
  "severity": "high",
  "provider": "twilio",
  "error_code": "31005",
  "source_event_id": "call_evt_xyz789"
}
```

---

## lead.stalled

**Alert type generated:** `lead_stalled_high_severity`

**Required fields:**

| Field          | Type      | Description                                                                  |
| -------------- | --------- | ---------------------------------------------------------------------------- |
| `severity`     | `string`  | Must be `"high"` to trigger an alert                                         |
| `days_stalled` | `integer` | Number of days the lead has been stalled. Must be `>= 3` to trigger an alert |

**Optional fields:**

| Field             | Type     | Description                                          |
| ----------------- | -------- | ---------------------------------------------------- |
| `source_event_id` | `string` | Custom dedup key; falls back to `event_id` if absent |
| `lead_id`         | `string` | CRM lead identifier                                  |
| `assigned_to`     | `string` | User or team the lead is assigned to                 |

**Example JSON:**

```json
{
  "severity": "high",
  "days_stalled": 7,
  "lead_id": "lead_001",
  "assigned_to": "sales_team_a",
  "source_event_id": "lead_stall_evt_456"
}
```

---

## appointment.no_show

**Alert type generated:** `appointment_no_show_high_severity`

**Required fields:**

| Field      | Type     | Description                          |
| ---------- | -------- | ------------------------------------ |
| `severity` | `string` | Must be `"high"` to trigger an alert |

**Optional fields:**

| Field             | Type     | Description                                          |
| ----------------- | -------- | ---------------------------------------------------- |
| `source_event_id` | `string` | Custom dedup key; falls back to `event_id` if absent |
| `appointment_id`  | `string` | CRM appointment identifier                           |
| `contact_id`      | `string` | CRM contact identifier                               |
| `scheduled_at`    | `string` | ISO-8601 timestamp of the original appointment       |

**Example JSON:**

```json
{
  "severity": "high",
  "appointment_id": "appt_777",
  "contact_id": "contact_222",
  "scheduled_at": "2026-04-05T14:00:00Z",
  "source_event_id": "no_show_evt_321"
}
```

---

## follow_up.missed

**Alert type generated:** `follow_up_missed_high_severity`

**Required fields:**

| Field      | Type     | Description                          |
| ---------- | -------- | ------------------------------------ |
| `severity` | `string` | Must be `"high"` to trigger an alert |

**Optional fields:**

| Field              | Type     | Description                                          |
| ------------------ | -------- | ---------------------------------------------------- |
| `source_event_id`  | `string` | Custom dedup key; falls back to `event_id` if absent |
| `contact_id`       | `string` | CRM contact identifier                               |
| `follow_up_due_at` | `string` | ISO-8601 timestamp when the follow-up was due        |
| `assigned_to`      | `string` | User or team responsible for the follow-up           |

**Example JSON:**

```json
{
  "severity": "high",
  "contact_id": "contact_555",
  "follow_up_due_at": "2026-04-03T09:00:00Z",
  "assigned_to": "rep_jane_doe",
  "source_event_id": "followup_missed_evt_888"
}
```

````

- [ ] **Step 8.2: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add docs/event_payload_schemas.md && git commit -m "docs: add event_payload_schemas.md for all 5 event types"
````

---

## Task 9: Update .env.example

**Files:**

- Modify: `.env.example`

**Context:** The current `.env.example` shows `DATABASE_URL=sqlite:///./nuatis_ops.db`. It needs to show a `postgres://` format example for Supabase.

- [ ] **Step 9.1: Update .env.example**

Read the current `.env.example` first, then update the `DATABASE_URL` line. The updated line should be:

```
DATABASE_URL=postgres://postgres.PROJECT_REF:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

Add a comment above showing the local fallback:

```
# Local SQLite fallback (used by tests):
# DATABASE_URL=sqlite:///./nuatis_ops.db
#
# Supabase PostgreSQL (production):
DATABASE_URL=postgres://postgres.PROJECT_REF:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

- [ ] **Step 9.2: Commit**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && git add .env.example && git commit -m "chore: update .env.example to show postgres:// DATABASE_URL for Supabase"
```

---

## Task 10: Final verification — run full test suite

**Files:** none (read-only)

- [ ] **Step 10.1: Run full test suite**

```bash
cd ~/Documents/Nuatis/Nuatis-Ops-Copilot && python -m unittest discover -s tests -v 2>&1
```

Expected output ends with something like:

```
----------------------------------------------------------------------
Ran XX tests in X.XXXs

OK
```

Zero failures, zero errors.

- [ ] **Step 10.2: If any test fails, diagnose before fixing**

Read the full error message. Common failure modes:

- `ImportError` on a new detector → check file path matches import
- `AttributeError: 'DatabaseConnection' object has no attribute 'row_factory'` → verify Task 2 removed `self._conn.row_factory = sqlite3.Row` from both repos
- `AssertionError: 2 != 5` on `detectors_run` → verify Task 7 updated all 3 assertions
- `ImportError: cannot import name 'DatabaseIntegrityError'` → verify Task 1 exported it from `db/connection.py`

---

## Spec Coverage Check (self-review)

| Spec requirement                                                             | Task covering it                                       |
| ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| Audit db layer (connection.py, migrations, settings)                         | Done before planning                                   |
| Update db/connection.py to use psycopg2                                      | Task 1                                                 |
| psycopg2 in requirements.txt                                                 | Task 1                                                 |
| Rewrite 6 migration files for Postgres                                       | Tasks 3 (0001, 0002); 0003-0006 verified compatible    |
| SERIAL/IDENTITY — not needed (no INTEGER PRIMARY KEY in existing migrations) | N/A                                                    |
| Keep unique partial indexes with WHERE status='open'                         | All preserved in Tasks 3-6                             |
| Keep tenant_id scoping                                                       | Unchanged                                              |
| DATABASE_URL in .env.example as postgres://                                  | Task 9                                                 |
| Keep SQLite for tests                                                        | All tasks use `connect("sqlite:///:memory:")` in tests |
| LeadStalledDetector (days_stalled >= 3)                                      | Task 4                                                 |
| AppointmentNoShowDetector                                                    | Task 5                                                 |
| FollowUpMissedDetector                                                       | Task 6                                                 |
| Migration 0007 (lead_stalled index)                                          | Task 4                                                 |
| Migration 0008 (appointment_no_show index)                                   | Task 5                                                 |
| Migration 0009 (follow_up_missed index)                                      | Task 6                                                 |
| Register 3 new detectors in orchestration                                    | Task 7                                                 |
| Tests: no_match wrong event_type                                             | Tasks 4-6                                              |
| Tests: no_match severity not high                                            | Tasks 4-6                                              |
| Tests: matched_created                                                       | Tasks 4-6                                              |
| Tests: matched_deduped (idempotent evaluate)                                 | Tasks 4-6                                              |
| Tests: matched_created again after resolve                                   | Tasks 4-6 (stateless detector note)                    |
| docs/event_payload_schemas.md for all 5 types                                | Task 8                                                 |
| All existing tests still pass                                                | Task 10                                                |
| Do not rename/move files                                                     | All tasks modify in place                              |
| Do not change HTTP API contracts                                             | No API files touched                                   |
| No new deps unless required                                                  | Only psycopg2-binary added                             |
