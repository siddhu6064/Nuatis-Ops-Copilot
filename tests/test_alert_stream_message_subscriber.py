import unittest
from typing import Any

from domain.internal_event_contracts import InternalEvent
from workers.events.alert_stream_message_subscriber import AlertStreamMessageSubscriber
from workers.events.inprocess_event_bus import InProcessInternalEventBus


class RecordingSink:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


class FailingSink:
    def send(self, message: dict[str, Any]) -> None:
        raise RuntimeError("sink failed")


class AlertStreamMessageSubscriberTests(unittest.TestCase):
    def test_alert_created_internal_event_becomes_expected_stream_message(self) -> None:
        sink = RecordingSink()
        subscriber = AlertStreamMessageSubscriber(sink)

        subscriber.handle(
            InternalEvent(
                event_type="alert_created",
                payload={
                    "ops_alert_id": "ops_1",
                    "tenant_id": "tenant_a",
                    "status": "open",
                    "alert_type": "booking_failure_high_severity",
                    "created_at": "2026-03-26T05:00:00Z",
                    "details_json": '{"severity":"high"}',
                },
            )
        )

        self.assertEqual(len(sink.messages), 1)
        self.assertEqual(
            sink.messages[0],
            {
                "event_type": "alert_created",
                "ops_alert_id": "ops_1",
                "tenant_id": "tenant_a",
                "status": "open",
                "alert_type": "booking_failure_high_severity",
                "created_at": "2026-03-26T05:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "details_json": '{"severity":"high"}',
            },
        )

    def test_alert_resolved_internal_event_becomes_expected_stream_message(self) -> None:
        sink = RecordingSink()
        subscriber = AlertStreamMessageSubscriber(sink)

        subscriber.handle(
            InternalEvent(
                event_type="alert_resolved",
                payload={
                    "ops_alert_id": "ops_2",
                    "tenant_id": "tenant_a",
                    "alert_type": "booking_failure_high_severity",
                    "created_at": "2026-03-26T05:01:00Z",
                    "resolved_at": "2026-03-26T05:10:00Z",
                    "resolved_by": "ops_user_1",
                    "details_json": '{"severity":"high"}',
                },
            )
        )

        self.assertEqual(len(sink.messages), 1)
        self.assertEqual(sink.messages[0]["event_type"], "alert_resolved")
        self.assertEqual(sink.messages[0]["status"], "resolved")
        self.assertEqual(sink.messages[0]["resolved_at"], "2026-03-26T05:10:00Z")
        self.assertEqual(sink.messages[0]["resolved_by"], "ops_user_1")

    def test_unsupported_event_type_is_ignored_safely(self) -> None:
        sink = RecordingSink()
        subscriber = AlertStreamMessageSubscriber(sink)

        subscriber.handle(
            InternalEvent(
                event_type="unsupported_event_type",  # type: ignore[arg-type]
                payload={"ops_alert_id": "ops_3", "tenant_id": "tenant_a"},
            )
        )

        self.assertEqual(sink.messages, [])

    def test_sink_failure_is_isolated_by_bus_and_core_publish_flow_continues(self) -> None:
        failing_subscriber = AlertStreamMessageSubscriber(FailingSink())
        recording_sink = RecordingSink()
        later_subscriber = AlertStreamMessageSubscriber(recording_sink)
        bus = InProcessInternalEventBus([failing_subscriber, later_subscriber])

        result = bus.publish(
            InternalEvent(
                event_type="alert_created",
                payload={
                    "ops_alert_id": "ops_4",
                    "tenant_id": "tenant_a",
                    "status": "open",
                },
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(len(recording_sink.messages), 1)
        self.assertEqual(recording_sink.messages[0]["event_type"], "alert_created")


if __name__ == "__main__":
    unittest.main()
