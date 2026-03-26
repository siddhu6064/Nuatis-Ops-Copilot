import unittest
from pathlib import Path

from db.connection import connect, disconnect
from domain.internal_event_contracts import InternalEvent
from domain.ops_alerts_service import OpsAlertsService
from repositories.ops_alerts_repository import OpsAlertsRepository
from workers.events.inprocess_event_bus import InProcessInternalEventBus


MIGRATION_PATH = Path("db/migrations/0002_create_ops_alerts.sql")
MIGRATION_0004_PATH = Path("db/migrations/0004_add_resolved_by_to_ops_alerts.sql")


class RecordingSubscriber:
    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list[InternalEvent] = []

    def handle(self, event: InternalEvent) -> None:
        self.events.append(event)


class FailingSubscriber:
    def __init__(self) -> None:
        self.calls = 0

    def handle(self, event: InternalEvent) -> None:
        self.calls += 1
        raise RuntimeError("subscriber failed")


class InProcessEventBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = connect("sqlite:///:memory:")
        self.db.connection.executescript(MIGRATION_PATH.read_text())
        self.db.connection.executescript(MIGRATION_0004_PATH.read_text())
        self.repo = OpsAlertsRepository(self.db)

    def tearDown(self) -> None:
        disconnect(self.db)

    def test_alert_created_event_reaches_multiple_subscribers(self) -> None:
        first = RecordingSubscriber("first")
        second = RecordingSubscriber("second")
        bus = InProcessInternalEventBus([first, second])
        service = OpsAlertsService(self.repo, event_publisher=bus)

        created = service.create_ops_alert(
            {
                "ops_alert_id": "bus_alert_1",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        self.assertEqual(created["result"], "created")
        self.assertEqual(len(first.events), 1)
        self.assertEqual(len(second.events), 1)
        self.assertEqual(first.events[0].event_type, "alert_created")
        self.assertEqual(second.events[0].event_type, "alert_created")

    def test_alert_resolved_event_reaches_subscribers(self) -> None:
        subscriber = RecordingSubscriber("only")
        bus = InProcessInternalEventBus([subscriber])
        service = OpsAlertsService(self.repo, event_publisher=bus)
        service.create_ops_alert(
            {
                "ops_alert_id": "bus_alert_2",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        resolved = service.resolve_ops_alert(
            tenant_id="tenant_a",
            ops_alert_id="bus_alert_2",
            resolved_at="2026-03-26T04:00:00Z",
        )

        self.assertTrue(resolved)
        self.assertEqual([event.event_type for event in subscriber.events], ["alert_created", "alert_resolved"])

    def test_subscriber_failure_is_isolated_and_later_subscriber_still_receives(self) -> None:
        failing = FailingSubscriber()
        later = RecordingSubscriber("later")
        bus = InProcessInternalEventBus([failing, later])
        service = OpsAlertsService(self.repo, event_publisher=bus)

        created = service.create_ops_alert(
            {
                "ops_alert_id": "bus_alert_3",
                "tenant_id": "tenant_a",
                "alert_type": "workflow_failure",
                "status": "open",
            }
        )

        self.assertEqual(created["result"], "created")
        self.assertEqual(failing.calls, 1)
        self.assertEqual(len(later.events), 1)
        self.assertEqual(later.events[0].event_type, "alert_created")

    def test_no_subscribers_is_safe_noop(self) -> None:
        bus = InProcessInternalEventBus([])

        result = bus.publish(
            InternalEvent(
                event_type="alert_created",
                payload={"ops_alert_id": "none", "tenant_id": "tenant_a"},
            )
        )

        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
