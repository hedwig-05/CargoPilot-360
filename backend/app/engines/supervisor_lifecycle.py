from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    AgentWorkflow,
    AgentRun,
    SupervisorWorkflowLink,
)


TERMINAL_WORKFLOW_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


def register_supervisor_exception_workflow(
    db: Session,
    supervisor_workflow_id: int,
    exception_workflow_id: int,
    exception_id: int,
    action_id: int = None,
):
    """Create or update a Supervisor-to-exception workflow association."""

    link = (
        db.query(SupervisorWorkflowLink)
        .filter(
            SupervisorWorkflowLink.supervisor_workflow_id
            == supervisor_workflow_id,
            SupervisorWorkflowLink.exception_workflow_id
            == exception_workflow_id,
        )
        .with_for_update()
        .first()
    )

    if link is None:
        link = SupervisorWorkflowLink(
            supervisor_workflow_id=supervisor_workflow_id,
            exception_workflow_id=exception_workflow_id,
            exception_id=exception_id,
            action_id=action_id,
        )
        db.add(link)
    elif action_id is not None:
        link.action_id = action_id

    db.flush()
    return link


def refresh_supervisor_workflow_status(
    db: Session,
    supervisor_workflow_id: int,
    current_time=None,
):
    """
    Recalculate a Supervisor's lifecycle from every exception workflow
    it coordinates. A Supervisor cannot complete while any linked
    exception workflow remains active or awaiting approval.
    """

    current_time = current_time or datetime.now()

    supervisor = (
        db.query(AgentWorkflow)
        .filter(
            AgentWorkflow.workflow_id == supervisor_workflow_id
        )
        .with_for_update()
        .first()
    )

    if supervisor is None:
        return None

    links = (
        db.query(SupervisorWorkflowLink)
        .filter(
            SupervisorWorkflowLink.supervisor_workflow_id
            == supervisor_workflow_id
        )
        .order_by(SupervisorWorkflowLink.link_id.asc())
        .all()
    )

    summaries = []
    child_statuses = []

    for link in links:
        child = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == link.exception_workflow_id
            )
            .first()
        )

        status = child.status if child else "FAILED"
        child_statuses.append(status)

        summaries.append({
            "exception_id": link.exception_id,
            "exception_workflow_id": link.exception_workflow_id,
            "action_id": link.action_id,
            "status": status,
            "current_node": child.current_node if child else "WORKFLOW_NOT_FOUND",
            "error": child.error_message if child else "Linked workflow not found.",
        })

    active_statuses = [
        status for status in child_statuses
        if status not in TERMINAL_WORKFLOW_STATUSES
    ]

    if active_statuses:
        if "WAITING_FOR_APPROVAL" in active_statuses:
            supervisor.status = "WAITING_FOR_APPROVAL"
            supervisor.current_node = "WAITING_FOR_EXCEPTION_APPROVALS"
        else:
            supervisor.status = "RUNNING"
            supervisor.current_node = "WAITING_FOR_EXCEPTION_WORKFLOWS"
        supervisor.completed_at = None
        run_status = (
            "WAITING_FOR_APPROVAL"
            if supervisor.status == "WAITING_FOR_APPROVAL"
            else "PROCESSING"
        )
    elif "FAILED" in child_statuses:
        supervisor.status = "FAILED"
        supervisor.current_node = "SUPERVISOR_EXCEPTION_WORKFLOW_FAILED"
        supervisor.completed_at = current_time
        run_status = "FAILED"
    elif "CANCELLED" in child_statuses:
        supervisor.status = "CANCELLED"
        supervisor.current_node = "SUPERVISOR_CANCELLED"
        supervisor.completed_at = current_time
        run_status = "COMPLETED"
    else:
        supervisor.status = "COMPLETED"
        supervisor.current_node = "SUPERVISOR_COMPLETED"
        supervisor.completed_at = current_time
        run_status = "COMPLETED"

    supervisor_run = (
        db.query(AgentRun)
        .filter(
            AgentRun.workflow_id == supervisor_workflow_id,
            AgentRun.agent_type == "SUPERVISOR",
        )
        .order_by(AgentRun.step_no.desc())
        .with_for_update()
        .first()
    )

    if supervisor_run:
        output = dict(supervisor_run.output_data or {})

        action_outcomes = output.get("action_outcomes") or []
        has_unverified_resolution = any(
            not outcome.get("resolution_verified", False)
            for outcome in action_outcomes
        )

        if (
            supervisor.status == "COMPLETED"
            and has_unverified_resolution
        ):
            supervisor.current_node = (
                "SUPERVISOR_COMPLETED_WITH_UNVERIFIED_RESOLUTIONS"
            )

        output["supervisor_completion_quality"] = (
            "COMPLETED_WITH_UNVERIFIED_RESOLUTIONS"
            if supervisor.status == "COMPLETED" and has_unverified_resolution
            else "COMPLETED"
            if supervisor.status == "COMPLETED"
            else supervisor.status
        )
        output["exception_workflow_summary"] = summaries
        output["exception_workflows_total"] = len(summaries)
        output["exception_workflows_terminal"] = sum(
            status in TERMINAL_WORKFLOW_STATUSES
            for status in child_statuses
        )
        output["exception_workflows_outstanding"] = len(active_statuses)
        output["exception_workflows_failed"] = child_statuses.count("FAILED")
        supervisor_run.output_data = output
        supervisor_run.execution_status = run_status
        supervisor_run.completed_at = (
            None if run_status in {"PROCESSING", "WAITING_FOR_APPROVAL"}
            else current_time
        )

    db.flush()

    return {
        "workflow_id": supervisor_workflow_id,
        "workflow_status": supervisor.status,
        "current_node": supervisor.current_node,
        "total_exception_workflows": len(summaries),
        "terminal_exception_workflows": sum(
            status in TERMINAL_WORKFLOW_STATUSES
            for status in child_statuses
        ),
        "outstanding_exception_workflows": len(active_statuses),
        "failed_exception_workflows": child_statuses.count("FAILED"),
        "exception_workflows": summaries,
    }



def refresh_supervisors_for_action(
    db: Session,
    action_id: int,
    current_time=None,
):
    """Refresh every Supervisor workflow associated with an action."""

    links = (
        db.query(SupervisorWorkflowLink)
        .filter(SupervisorWorkflowLink.action_id == action_id)
        .all()
    )

    results = []
    seen_workflow_ids = set()

    for link in links:
        if link.supervisor_workflow_id in seen_workflow_ids:
            continue

        seen_workflow_ids.add(link.supervisor_workflow_id)
        result = refresh_supervisor_workflow_status(
            db=db,
            supervisor_workflow_id=link.supervisor_workflow_id,
            current_time=current_time,
        )
        if result:
            results.append(result)

    return results
