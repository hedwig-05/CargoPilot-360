import unittest
from types import SimpleNamespace

from app.engines.action_executor import (
    action_payload_priority,
    execute_simulated_action,
)


def make_action(action_type, payload=None):
    return SimpleNamespace(
        action_type=action_type,
        action_payload=payload or {},
    )


def make_shipment():
    return SimpleNamespace(
        shipment_ref="CP-TEST-001",
        status="IN_TRANSIT",
        assigned_user_id=2,
    )


class ActionSimulationRegressionTests(unittest.TestCase):

    def test_email_action_is_only_prepared_not_sent(self):
        result = execute_simulated_action(
            make_action(
                "SEND_FOLLOW_UP_EMAIL",
                {"recipient": "operations@example.test"},
            ),
            make_shipment(),
            None,
        )

        self.assertTrue(result["simulation"])
        self.assertFalse(result["email_sent"])
        self.assertEqual(
            result["recipient"],
            "operations@example.test",
        )

    def test_operations_notification_is_not_sent(self):
        result = execute_simulated_action(
            make_action("NOTIFY_OPERATIONS_OFFICER"),
            make_shipment(),
            None,
        )

        self.assertTrue(result["simulation"])
        self.assertFalse(result["notification_sent"])
        self.assertEqual(result["assigned_user_id"], 2)

    def test_manager_escalation_is_not_sent(self):
        result = execute_simulated_action(
            make_action("ESCALATE_TO_MANAGER", {"priority": "URGENT"}),
            make_shipment(),
            None,
        )

        self.assertTrue(result["simulation"])
        self.assertFalse(result["escalation_sent"])
        self.assertEqual(result["priority"], "URGENT")

    def test_internal_notification_is_not_sent(self):
        result = execute_simulated_action(
            make_action("CREATE_NOTIFICATION"),
            make_shipment(),
            None,
        )

        self.assertTrue(result["simulation"])
        self.assertFalse(result["notification_sent"])

    def test_shipment_status_update_records_before_and_after(self):
        shipment = make_shipment()

        result = execute_simulated_action(
            make_action(
                "UPDATE_SHIPMENT_STATUS",
                {"new_status": "ON_HOLD"},
            ),
            shipment,
            None,
        )

        self.assertEqual(result["previous_status"], "IN_TRANSIT")
        self.assertEqual(result["new_status"], "ON_HOLD")
        self.assertEqual(shipment.status, "ON_HOLD")
        self.assertTrue(result["simulation"])

    def test_invalid_shipment_status_is_rejected_without_mutation(self):
        shipment = make_shipment()

        with self.assertRaisesRegex(ValueError, "valid new_status"):
            execute_simulated_action(
                make_action(
                    "UPDATE_SHIPMENT_STATUS",
                    {"new_status": "FLYING"},
                ),
                shipment,
                None,
            )

        self.assertEqual(shipment.status, "IN_TRANSIT")

    def test_document_correction_can_reference_exception(self):
        exception = SimpleNamespace(exception_id=42)

        result = execute_simulated_action(
            make_action("REQUEST_DOCUMENT_CORRECTION"),
            make_shipment(),
            exception,
        )

        self.assertEqual(result["exception_id"], 42)
        self.assertTrue(result["simulation"])

    def test_action_priority_defaults_and_customizes(self):
        self.assertEqual(
            action_payload_priority(make_action("ESCALATE_TO_MANAGER")),
            "NORMAL",
        )
        self.assertEqual(
            action_payload_priority(
                make_action("ESCALATE_TO_MANAGER", {"priority": "URGENT"})
            ),
            "URGENT",
        )


if __name__ == "__main__":
    unittest.main()
