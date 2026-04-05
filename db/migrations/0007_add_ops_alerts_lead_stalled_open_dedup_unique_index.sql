CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_lead_stalled_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'lead_stalled_high_severity'
      AND source_event_id IS NOT NULL;
