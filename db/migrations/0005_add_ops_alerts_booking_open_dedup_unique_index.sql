CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_booking_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'booking_failure_high_severity'
      AND source_event_id IS NOT NULL;
