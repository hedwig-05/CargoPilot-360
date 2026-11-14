
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AgentWorkflow, AgentRun


def update_dependent_workflows(
    db: Session,
    parent_workflow_id: int,
    outcome: str,
    current_time=None,
    error_message=None
):
    """
    Update workflows that depend on an action owned
    by the specified parent workflow.

    APPROVED:
        Dependents resume waiting for action execution.

    REJECTED:
        Dependents complete with a rejection outcome.

    SUCCEEDED:
        Dependents complete successfully.

    FAILED:
        Dependents fail with the parent's execution error.
    """

    current_time = current_time or datetime.now()

    outcome_mapping = {
        "APPROVED": {
            "status": "RUNNING",
            "current_node": "WAITING_FOR_PARENT_ACTION",
            "run_status": "PROCESSING",
            "completed_at": None
        },
        "REJECTED": {
            "status": "COMPLETED",
            "current_node": "PARENT_ACTION_REJECTED",
            "run_status": "COMPLETED",
            "completed_at": current_time
        },
        "SUCCEEDED": {
            "status": "COMPLETED",
            "current_node": "PARENT_ACTION_COMPLETED",
            "run_status": "COMPLETED",
            "completed_at": current_time
        },
        "FAILED": {
            "status": "FAILED",
            "current_node": "PARENT_ACTION_FAILED",
            "run_status": "FAILED",
            "completed_at": current_time
        }
    }

    if outcome not in outcome_mapping:
        raise ValueError(
            f"Unsupported dependency outcome: {outcome}"
        )

    configuration = outcome_mapping[outcome]

    dependent_workflows = (
        db.query(AgentWorkflow)
        .filter(
            AgentWorkflow.parent_workflow_id
            == parent_workflow_id
        )
        .with_for_update()
        .all()
    )

    updated_count = 0

    for workflow in dependent_workflows:

        workflow.status = configuration["status"]

        workflow.current_node = configuration["current_node"]

        workflow.completed_at = configuration["completed_at"]

        workflow.error_message = (
            error_message if outcome == "FAILED" else None
        )

        supervisor_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.workflow_id == workflow.workflow_id,
                AgentRun.agent_type == "SUPERVISOR"
            )
            .order_by(AgentRun.step_no.desc())
            .with_for_update()
            .first()
        )

        if supervisor_run:

            supervisor_run.execution_status = (
                configuration["run_status"]
            )

            supervisor_run.completed_at = (
                configuration["completed_at"]
            )

            supervisor_run.error_message = (
                error_message if outcome == "FAILED" else None
            )

            output = dict(supervisor_run.output_data or {})

            output["dependency_outcome"] = outcome
            output["parent_workflow_id"] = parent_workflow_id

            if error_message:
                output["dependency_error"] = error_message

            supervisor_run.output_data = output

        updated_count += 1

    return updated_count
