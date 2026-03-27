CREATE INDEX IF NOT EXISTS idx_ops_alerts_open_dedup_lookup
    ON ops_alerts (tenant_id, alert_type, source_event_id, status);
