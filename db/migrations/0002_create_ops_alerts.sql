CREATE TABLE IF NOT EXISTS ops_alerts (
    ops_alert_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_activity_event_id TEXT,
    source_event_id TEXT,
    alert_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
