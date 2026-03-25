import unittest
from pathlib import Path

from api.activity_events_endpoint import ENDPOINT_PATH, ingest_activity_event
from db.connection import connect, disconnect
from repositories.activity_events_repository import ActivityEventsRepository
from repositories.ops_alerts_repository import OpsAlertsRepository


ACTIVITY_EVENTS_MIGRATION_PATH = Path("db/migrations/0001_create_activity_events.sql")
OPS_ALERTS_MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")


class ActivityEventsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(ACTIVITY_EVENTS_MIGRATION_PATH.read_text())
        self.db.connection.executescript(OPS_ALERTS_MIGRATION_PATH.read_text())
        self.events_repo = ActivityEventsRepository(self.db)
        self.alerts_repo = OpsAlertsRepository(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_successful_ingest_non_matching_persists_event_and_returns_zero_matches(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_1",
                "tenant_id": "tenant_1",
                "event_id": "evt_1",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:00:00Z",
                "payload_json": '{"duration": 90}',
            },
            self.db,
        )

        self.assertEqual(status, 201)
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["detector_summary"]["matches"], 0)
        self.assertEqual(response["data"]["detector_summary"]["alerts_created"], 0)

        stored = self.events_repo.get_event_by_id("tenant_1", "ing_1")
        self.assertIsNotNone(stored)
        self.assertEqual(len(self.alerts_repo.list_alerts_by_tenant("tenant_1")), 0)

    def test_successful_ingest_matching_persists_event_and_returns_match_and_alert(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_2",
                "tenant_id": "tenant_1",
                "event_id": "evt_2",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T20:05:00Z",
                "payload_json": '{"severity":"high"}',
            },
            self.db,
        )

        self.assertEqual(status, 201)
        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["detector_summary"]["matches"], 1)
        self.assertEqual(response["data"]["detector_summary"]["alerts_created"], 1)

        stored_event = self.events_repo.get_event_by_id("tenant_1", "ing_2")
        self.assertIsNotNone(stored_event)
        alerts = self.alerts_repo.list_alerts_by_tenant("tenant_1")
        self.assertEqual(len(alerts), 1)

    def test_duplicate_event_returns_conflict_and_does_not_run_detectors(self) -> None:
        payload = {
            "activity_event_id": "ing_3",
            "tenant_id": "tenant_1",
            "event_id": "evt_dup",
            "event_type": "call.completed",
            "event_source": "voice",
            "occurred_at": "2026-03-25T20:10:00Z",
            "payload_json": '{}',
        }

        first_status, first_response = ingest_activity_event(payload, self.db)
        second_status, second_response = ingest_activity_event(
            {**payload, "activity_event_id": "ing_4"},
            self.db,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(first_response["data"]["detector_summary"]["alerts_created"], 0)
        self.assertEqual(second_status, 409)
        self.assertFalse(second_response["success"])
        self.assertEqual(second_response["error"]["code"], "duplicate_event")
        self.assertEqual(
            second_response["error"]["message"],
            "An event with the same tenant_id and event_id already exists.",
        )
        self.assertEqual(len(self.alerts_repo.list_alerts_by_tenant("tenant_1")), 0)

    def test_duplicate_activity_event_id_returns_specific_conflict_message(self) -> None:
        first_status, _ = ingest_activity_event(
            {
                "activity_event_id": "ing_dup_id",
                "tenant_id": "tenant_1",
                "event_id": "evt_10",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:12:00Z",
                "payload_json": '{}',
            },
            self.db,
        )
        second_status, second_response = ingest_activity_event(
            {
                "activity_event_id": "ing_dup_id",
                "tenant_id": "tenant_2",
                "event_id": "evt_11",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:13:00Z",
                "payload_json": '{}',
            },
            self.db,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 409)
        self.assertEqual(second_response["error"]["code"], "duplicate_event")
        self.assertEqual(
            second_response["error"]["message"],
            "An event with this activity_event_id already exists.",
        )

    def test_payload_json_empty_dict_does_not_fail_required_validation(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_4",
                "tenant_id": "tenant_1",
                "event_id": "evt_4",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:14:00Z",
                "payload_json": {},
            },
            self.db,
        )

        self.assertEqual(status, 201)
        self.assertTrue(response["success"])

    def test_missing_required_field_returns_validation_error(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_5",
                "event_id": "evt_5",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "2026-03-25T20:15:00Z",
                "payload_json": "{}",
            },
            self.db,
        )

        self.assertEqual(status, 400)
        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "validation_error")

    def test_tenant_scoped_behavior_remains_correct_end_to_end(self) -> None:
        self.assertEqual(ENDPOINT_PATH, "/internal/events/activity")

        alpha_status, alpha_response = ingest_activity_event(
            {
                "activity_event_id": "ing_6",
                "tenant_id": "tenant_alpha",
                "event_id": "evt_alpha",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T20:20:00Z",
                "payload_json": '{"severity":"high"}',
            },
            self.db,
        )
        beta_status, beta_response = ingest_activity_event(
            {
                "activity_event_id": "ing_7",
                "tenant_id": "tenant_beta",
                "event_id": "evt_beta",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T20:21:00Z",
                "payload_json": '{"severity":"high"}',
            },
            self.db,
        )

        self.assertEqual(alpha_status, 201)
        self.assertEqual(beta_status, 201)

        alpha_alert_id = alpha_response["data"]["detector_summary"]["results"][0]["ops_alert_id"]
        beta_alert_id = beta_response["data"]["detector_summary"]["results"][0]["ops_alert_id"]

        alpha_alert = self.alerts_repo.get_alert_by_id("tenant_alpha", alpha_alert_id)
        beta_alert = self.alerts_repo.get_alert_by_id("tenant_beta", beta_alert_id)
        cross_tenant = self.alerts_repo.get_alert_by_id("tenant_alpha", beta_alert_id)

        self.assertIsNotNone(alpha_alert)
        self.assertIsNotNone(beta_alert)
        self.assertIsNone(cross_tenant)

    def test_detector_summary_reflects_deduped_match(self) -> None:
        first_status, first_response = ingest_activity_event(
            {
                "activity_event_id": "ing_dedup_1",
                "tenant_id": "tenant_1",
                "event_id": "evt_unique_a",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T20:30:00Z",
                "payload_json": '{"severity":"high","source_event_id":"dedup_source"}',
            },
            self.db,
        )
        second_status, second_response = ingest_activity_event(
            {
                "activity_event_id": "ing_dedup_2",
                "tenant_id": "tenant_1",
                "event_id": "evt_unique_b",
                "event_type": "booking.failed",
                "event_source": "scheduler",
                "occurred_at": "2026-03-25T20:31:00Z",
                "payload_json": '{"severity":"high","source_event_id":"dedup_source"}',
            },
            self.db,
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 201)
        self.assertEqual(first_response["data"]["detector_summary"]["results"][0]["result"], "matched_created")
        self.assertEqual(second_response["data"]["detector_summary"]["results"][0]["result"], "matched_deduped")
        self.assertEqual(second_response["data"]["detector_summary"]["alerts_created"], 0)
        self.assertEqual(second_response["data"]["detector_summary"]["alerts_deduped"], 1)


    def test_invalid_occurred_at_returns_validation_error(self) -> None:
        status, response = ingest_activity_event(
            {
                "activity_event_id": "ing_bad_time",
                "tenant_id": "tenant_1",
                "event_id": "evt_bad_time",
                "event_type": "call.completed",
                "event_source": "voice",
                "occurred_at": "not-a-timestamp",
                "payload_json": "{}",
            },
            self.db,
        )

        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "validation_error")



if __name__ == "__main__":
    unittest.main()
