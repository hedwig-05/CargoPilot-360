"""Safe entry-point regressions for the API-driven Supervisor service.

These tests exercise precondition handling without connecting to MySQL or
running document, investigation, risk, planning, or action side effects.

Run from the backend directory:
    python -m unittest test_supervisor_entrypoint_regression -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.engines.supervisor_agent import run_supervisor, continue_supervisor


def make_db(first_result):
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = first_result
    db.query.return_value = query
    return db


class SupervisorEntryPointRegressionTests(unittest.TestCase):

    def test_missing_shipment_is_rejected_before_workflow_creation(self):
        db = make_db(None)

        with self.assertRaisesRegex(ValueError, "Shipment 999 was not found"):
            run_supervisor(db=db, shipment_id=999)

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_delivered_shipment_is_rejected_before_workflow_creation(self):
        shipment = SimpleNamespace(
            shipment_id=10,
            shipment_ref="CP-TEST-DELIVERED",
            status="DELIVERED",
        )
        db = make_db(shipment)

        with self.assertRaisesRegex(ValueError, "delivered shipment"):
            run_supervisor(db=db, shipment_id=10)

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_cancelled_shipment_is_rejected_before_workflow_creation(self):
        shipment = SimpleNamespace(
            shipment_id=11,
            shipment_ref="CP-TEST-CANCELLED",
            status="CANCELLED",
        )
        db = make_db(shipment)

        with self.assertRaisesRegex(ValueError, "cancelled or delivered"):
            run_supervisor(db=db, shipment_id=11)

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_missing_action_is_rejected_before_execution(self):
        db = make_db(None)

        with self.assertRaisesRegex(ValueError, "Action 404 was not found"):
            continue_supervisor(db=db, action_id=404)

        db.commit.assert_not_called()

    def test_unapproved_action_is_rejected_before_execution(self):
        action = SimpleNamespace(
            action_id=21,
            approval_status="PENDING",
            execution_status="NOT_STARTED",
        )
        db = make_db(action)

        with self.assertRaisesRegex(ValueError, "must be approved"):
            continue_supervisor(db=db, action_id=21)

        db.commit.assert_not_called()

    def test_successfully_executed_action_cannot_be_replayed(self):
        action = SimpleNamespace(
            action_id=22,
            approval_status="APPROVED",
            execution_status="SUCCEEDED",
        )
        db = make_db(action)

        with self.assertRaisesRegex(ValueError, "already been executed"):
            continue_supervisor(db=db, action_id=22)

        db.commit.assert_not_called()

    def test_failed_or_in_progress_action_cannot_be_continued(self):
        for status in ("EXECUTING", "FAILED", "SKIPPED"):
            with self.subTest(execution_status=status):
                action = SimpleNamespace(
                    action_id=23,
                    approval_status="APPROVED",
                    execution_status=status,
                )
                db = make_db(action)

                with self.assertRaisesRegex(
                    ValueError,
                    "cannot be continued from its current execution status",
                ):
                    continue_supervisor(db=db, action_id=23)

                db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
