CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_follow_up_missed_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'follow_up_missed_high_severity'
      AND source_event_id IS NOT NULL;
