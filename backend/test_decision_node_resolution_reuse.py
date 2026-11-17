"""Regression tests for Supervisor decision-node resolution-plan reuse.

These tests isolate the decision node from MySQL and the resolution planner.
Run from the backend directory with:
    python -m unittest test_decision_node_resolution_reuse -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents import graph
from app.models import Action, AgentWorkflow, ResolutionPlan


def make_query(first_result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = first_result
    return query


class DecisionNodeResolutionReuseTests(unittest.TestCase):

    def make_state(self, workflow_id=300):
        return {
            "workflow_id": workflow_id,
            "supervisor_run_id": 900,
            "exception_details": [
                {"exception_id": 44, "shipment_id": 12,
                 "exception_type": "DOCUMENT_MISMATCH"}
            ],
            "errors": [],
        }

    @patch.object(graph, "update_agent_run")
    @patch.object(graph, "create_child_run")
    @patch.object(graph, "SessionLocal")
    def test_reuses_plan_and_action_owned_by_another_workflow(
        self, session_local, create_child_run, update_agent_run
    ):
        current_workflow = SimpleNamespace(
            workflow_id=300, current_node=None, parent_workflow_id=None
        )
        existing_plan = SimpleNamespace(
            plan_id=71, workflow_id=200, version_no=2,
            priority="HIGH", status="PENDING_APPROVAL"
        )
        existing_action = SimpleNamespace(
            action_id=81, action_type="REQUEST_DOCUMENT_CORRECTION",
            approval_status="PENDING", execution_status="NOT_STARTED"
        )
        decision_run = SimpleNamespace(run_id=901)

        db = MagicMock()
        db.query.side_effect = [
            make_query(current_workflow),
            make_query(existing_plan),
            make_query(existing_action),
        ]
        session_local.return_value = db
        create_child_run.return_value = decision_run

        result = graph.decision_node(self.make_state())

        self.assertEqual(result["workflow_status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(len(result["resolution_results"]), 1)
        reused = result["resolution_results"][0]
        self.assertTrue(reused["reused_existing"])
        self.assertEqual(reused["plan_id"], 71)
        self.assertEqual(reused["action_id"], 81)
        self.assertEqual(reused["workflow_id"], 200)
        self.assertEqual(current_workflow.parent_workflow_id, 200)
        create_child_run.assert_called_once()
        update_agent_run.assert_called_once()
        db.commit.assert_called()
        db.close.assert_called_once()

    @patch.object(graph, "create_resolution_plan")
    @patch.object(graph, "SessionLocal")
    def test_creates_plan_when_no_active_plan_is_found(
        self, session_local, create_resolution_plan
    ):
        current_workflow = SimpleNamespace(
            workflow_id=300, current_node=None, parent_workflow_id=None
        )
        workflow_query = make_query(current_workflow)
        plan_query = make_query(None)

        db = MagicMock()
        db.query.side_effect = [workflow_query, plan_query]
        session_local.return_value = db
        create_resolution_plan.return_value = {
            "exception_id": 44,
            "workflow_id": 300,
            "plan_id": 72,
            "action_id": 82,
            "plan_status": "PENDING_APPROVAL",
        }

        result = graph.decision_node(self.make_state())

        self.assertEqual(len(result["resolution_results"]), 1)
        created = result["resolution_results"][0]
        self.assertFalse(created["reused_existing"])
        self.assertEqual(created["plan_id"], 72)
        self.assertEqual(created["action_id"], 82)
        create_resolution_plan.assert_called_once_with(
            db=db, exception_id=44
        )

        # Closed/resolved plans are deliberately not part of the active
        # status filter, so they do not prevent creation of a new plan.
        plan_filter = plan_query.filter.call_args
        self.assertIsNotNone(plan_filter)
        status_expression = plan_filter.args[1]
        self.assertEqual(
            list(status_expression.right.value),
            ["DRAFT", "PENDING_APPROVAL", "APPROVED", "EXECUTING"],
        )
        db.close.assert_called_once()

    @patch.object(graph, "create_child_run")
    @patch.object(graph, "SessionLocal")
    def test_active_plan_without_action_returns_failure(
        self, session_local, create_child_run
    ):
        current_workflow = SimpleNamespace(
            workflow_id=300, current_node=None, parent_workflow_id=None
        )
        existing_plan = SimpleNamespace(
            plan_id=71, workflow_id=300, version_no=1,
            priority="MEDIUM", status="APPROVED"
        )

        db = MagicMock()
        db.query.side_effect = [
            make_query(current_workflow),
            make_query(existing_plan),
            make_query(None),
        ]
        session_local.return_value = db

        result = graph.decision_node(self.make_state())

        self.assertEqual(result["workflow_status"], "FAILED")
        self.assertTrue(
            any("has no associated action" in error
                for error in result["errors"])
        )
        create_child_run.assert_not_called()
        db.rollback.assert_called()
        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
