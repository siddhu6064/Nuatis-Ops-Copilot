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
