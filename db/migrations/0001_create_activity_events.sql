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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_events_tenant_id
    ON activity_events (tenant_id);

CREATE INDEX IF NOT EXISTS idx_activity_events_event_type
    ON activity_events (event_type);

CREATE INDEX IF NOT EXISTS idx_activity_events_occurred_at
    ON activity_events (occurred_at);
