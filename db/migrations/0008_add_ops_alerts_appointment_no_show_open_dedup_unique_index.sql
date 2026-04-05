CREATE UNIQUE INDEX IF NOT EXISTS uq_ops_alerts_appointment_no_show_open_dedup
    ON ops_alerts (tenant_id, alert_type, source_event_id)
    WHERE status = 'open'
      AND alert_type = 'appointment_no_show_high_severity'
      AND source_event_id IS NOT NULL;
