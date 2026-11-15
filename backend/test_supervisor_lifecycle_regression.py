import unittest
from datetime import datetime
from types import SimpleNamespace

from app.engines.supervisor_lifecycle import (
    refresh_supervisor_workflow_status,
)
from app.models import AgentWorkflow, AgentRun, SupervisorWorkflowLink


class FakeQuery:
    def __init__(self, model, records):
        self.model = model
        self.records = records
        self.criteria = []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def _matches(self, record):
        for criterion in self.criteria:
            key = getattr(getattr(criterion, "left", None), "key", None)
            right = getattr(criterion, "right", None)
            expected = getattr(right, "value", None)
            if key is not None and getattr(record, key, object()) != expected:
                return False
        return True

    def all(self):
        return [record for record in self.records if self._matches(record)]

    def first(self):
        records = self.all()
        return records[0] if records else None


class FakeDB:
    def __init__(self, workflows, runs, links):
        self.records = {
            AgentWorkflow: workflows,
            AgentRun: runs,
            SupervisorWorkflowLink: links,
        }

    def query(self, model):
        return FakeQuery(model, self.records.get(model, []))

    def flush(self):
        pass


def make_workflow(workflow_id, status, current_node=None):
    return SimpleNamespace(
        workflow_id=workflow_id,
        status=status,
        current_node=current_node or status,
        completed_at=None,
        error_message=None,
    )


def make_run():
    return SimpleNamespace(
        workflow_id=100,
        agent_type="SUPERVISOR",
        step_no=1,
        output_data={"initial": True},
        execution_status="PROCESSING",
        completed_at=None,
    )


def make_link(link_id, exception_workflow_id, exception_id, action_id):
    return SimpleNamespace(
        link_id=link_id,
        supervisor_workflow_id=100,
        exception_workflow_id=exception_workflow_id,
        exception_id=exception_id,
        action_id=action_id,
    )


class SupervisorLifecycleRegressionTests(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2026, 11, 15, 12, 0, 0)
        self.supervisor = make_workflow(100, "WAITING_FOR_APPROVAL")
        self.run = make_run()

    def make_db(self, child_statuses):
        children = [
            make_workflow(workflow_id, status, f"NODE_{workflow_id}")
            for workflow_id, status in child_statuses
        ]
        links = [
            make_link(index, workflow_id, index + 40, index + 70)
            for index, (workflow_id, _) in enumerate(child_statuses, start=1)
        ]
        return FakeDB([self.supervisor] + children, [self.run], links)

    def test_supervisor_waits_until_every_exception_workflow_is_terminal(self):
        db = self.make_db([
            (201, "COMPLETED"),
            (202, "WAITING_FOR_APPROVAL"),
        ])

        result = refresh_supervisor_workflow_status(
            db, 100, current_time=self.now
        )

        self.assertEqual(result["workflow_status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(result["total_exception_workflows"], 2)
        self.assertEqual(result["terminal_exception_workflows"], 1)
        self.assertEqual(result["outstanding_exception_workflows"], 1)
        self.assertIsNone(self.supervisor.completed_at)
        self.assertEqual(self.run.execution_status, "WAITING_FOR_APPROVAL")
        self.assertIsNone(self.run.completed_at)

    def test_supervisor_completes_when_all_exception_workflows_are_terminal(self):
        db = self.make_db([
            (201, "COMPLETED"),
            (202, "COMPLETED"),
        ])

        result = refresh_supervisor_workflow_status(
            db, 100, current_time=self.now
        )

        self.assertEqual(result["workflow_status"], "COMPLETED")
        self.assertEqual(result["terminal_exception_workflows"], 2)
        self.assertEqual(result["outstanding_exception_workflows"], 0)
        self.assertEqual(self.supervisor.completed_at, self.now)
        self.assertEqual(self.run.execution_status, "COMPLETED")
        self.assertEqual(self.run.completed_at, self.now)

    def test_failed_exception_workflow_fails_supervisor_after_all_are_terminal(self):
        db = self.make_db([
            (201, "COMPLETED"),
            (202, "FAILED"),
        ])

        result = refresh_supervisor_workflow_status(
            db, 100, current_time=self.now
        )

        self.assertEqual(result["workflow_status"], "FAILED")
        self.assertEqual(result["failed_exception_workflows"], 1)
        self.assertEqual(self.supervisor.current_node, "SUPERVISOR_EXCEPTION_WORKFLOW_FAILED")
        self.assertEqual(self.run.execution_status, "FAILED")

    def test_running_child_keeps_supervisor_running(self):
        db = self.make_db([
            (201, "RUNNING"),
            (202, "COMPLETED"),
        ])

        result = refresh_supervisor_workflow_status(
            db, 100, current_time=self.now
        )

        self.assertEqual(result["workflow_status"], "RUNNING")
        self.assertEqual(self.run.execution_status, "PROCESSING")
        self.assertIsNone(self.supervisor.completed_at)


if __name__ == "__main__":
    unittest.main()
