import unittest
from types import SimpleNamespace

from app.engines.workflow_dependencies import update_dependent_workflows
from app.models import AgentWorkflow, AgentRun


class FakeQuery:
    def __init__(self, model, workflows, runs):
        self.model = model
        self.workflows = workflows
        self.runs = runs

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def all(self):
        if self.model is AgentWorkflow:
            return self.workflows
        return []

    def first(self):
        if self.model is AgentRun:
            return self.runs[0] if self.runs else None
        return None


class FakeDB:
    def __init__(self, workflows, runs):
        self.workflows = workflows
        self.runs = runs

    def query(self, model):
        return FakeQuery(model, self.workflows, self.runs)


def make_workflow():
    return SimpleNamespace(
        workflow_id=20,
        status="WAITING_FOR_APPROVAL",
        current_node="WAITING_FOR_APPROVAL",
        completed_at=None,
        error_message="old error",
    )


def make_supervisor_run():
    return SimpleNamespace(
        workflow_id=21,
        agent_type="SUPERVISOR",
        step_no=1,
        execution_status="PROCESSING",
        completed_at=None,
        error_message="old error",
        output_data={"existing": "value", "dependency_error": "old error"},
    )


class WorkflowDependencyRegressionTests(unittest.TestCase):

    def setUp(self):
        self.now = __import__("datetime").datetime(2026, 11, 14, 12, 0, 0)
        self.workflow = make_workflow()
        self.run = make_supervisor_run()
        self.db = FakeDB([self.workflow], [self.run])

    def test_approved_dependency_resumes_workflow(self):
        count = update_dependent_workflows(
            self.db, 10, "APPROVED", current_time=self.now
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.workflow.status, "RUNNING")
        self.assertEqual(self.workflow.current_node, "WAITING_FOR_PARENT_ACTION")
        self.assertIsNone(self.workflow.completed_at)
        self.assertEqual(self.run.execution_status, "PROCESSING")
        self.assertIsNone(self.run.completed_at)

    def test_rejected_dependency_completes_workflow(self):
        count = update_dependent_workflows(
            self.db, 10, "REJECTED", current_time=self.now
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.workflow.status, "COMPLETED")
        self.assertEqual(self.workflow.current_node, "PARENT_ACTION_REJECTED")
        self.assertEqual(self.workflow.completed_at, self.now)
        self.assertEqual(self.run.execution_status, "COMPLETED")
        self.assertEqual(self.run.completed_at, self.now)

    def test_successful_parent_action_completes_dependency(self):
        count = update_dependent_workflows(
            self.db, 10, "SUCCEEDED", current_time=self.now
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.workflow.status, "COMPLETED")
        self.assertEqual(self.workflow.current_node, "PARENT_ACTION_COMPLETED")
        self.assertEqual(self.run.execution_status, "COMPLETED")

    def test_failed_parent_action_fails_dependency_with_reason(self):
        count = update_dependent_workflows(
            self.db,
            10,
            "FAILED",
            current_time=self.now,
            error_message="simulated execution failure",
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.workflow.status, "FAILED")
        self.assertEqual(self.workflow.current_node, "PARENT_ACTION_FAILED")
        self.assertEqual(self.workflow.error_message, "simulated execution failure")
        self.assertEqual(self.run.execution_status, "FAILED")
        self.assertEqual(self.run.error_message, "simulated execution failure")
        self.assertEqual(
            self.run.output_data["dependency_error"],
            "simulated execution failure",
        )

    def test_unsupported_outcome_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported dependency outcome"):
            update_dependent_workflows(self.db, 10, "UNKNOWN")

    def test_no_dependents_returns_zero(self):
        db = FakeDB([], [])
        self.assertEqual(
            update_dependent_workflows(db, 10, "SUCCEEDED", current_time=self.now),
            0,
        )

    def test_missing_supervisor_run_still_updates_workflow(self):
        db = FakeDB([self.workflow], [])
        count = update_dependent_workflows(
            db, 10, "SUCCEEDED", current_time=self.now
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.workflow.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
