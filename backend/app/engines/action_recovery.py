"""Deterministic failure classification for action-execution recovery.

This module does not execute retries or alter approved actions. It produces a
bounded, auditable recovery recommendation for the supervisor/manager.
"""

MAX_AUTOMATIC_ATTEMPTS = 2


def analyze_action_failure(
    error: Exception,
    attempt_no: int,
    side_effect_state: str = "UNKNOWN",
) -> dict:
    """Classify a failed attempt without allowing an LLM to override safety."""

    message = str(error).strip() or error.__class__.__name__
    error_type = error.__class__.__name__

    if side_effect_state not in {"NOT_COMMITTED", "COMMITTED", "UNKNOWN"}:
        side_effect_state = "UNKNOWN"

    if side_effect_state != "NOT_COMMITTED":
        return {
            "failure_category": "OUTCOME_UNCERTAIN",
            "recovery_decision": "MANUAL_REVIEW",
            "retry_allowed": False,
            "attempt_no": attempt_no,
            "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
            "side_effect_state": side_effect_state,
            "error_type": error_type,
            "error_message": message,
            "reason": (
                "The operation may already have produced an external effect. "
                "Automatic retry could duplicate that effect."
            ),
        }

    if isinstance(error, (TimeoutError, ConnectionError)):
        if attempt_no < MAX_AUTOMATIC_ATTEMPTS:
            return {
                "failure_category": "TRANSIENT",
                "recovery_decision": "RETRY_CANDIDATE",
                "retry_allowed": True,
                "attempt_no": attempt_no,
                "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
                "side_effect_state": side_effect_state,
                "error_type": error_type,
                "error_message": message,
                "reason": "A transient failure occurred before any side effect was committed.",
            }

        return {
            "failure_category": "RETRY_EXHAUSTED",
            "recovery_decision": "MANAGER_REVIEW",
            "retry_allowed": False,
            "attempt_no": attempt_no,
            "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
            "side_effect_state": side_effect_state,
            "error_type": error_type,
            "error_message": message,
            "reason": "The bounded automatic attempt limit has been reached.",
        }

    if isinstance(error, (ValueError, TypeError)):
        category = "INVALID_ACTION_OR_PAYLOAD"
        decision = "REPLAN_REQUIRED"
        reason = "The action or its payload is invalid and should not be repeated unchanged."
    elif isinstance(error, PermissionError):
        category = "PERMISSION"
        decision = "MANAGER_REVIEW"
        reason = "The operation was not authorised; a manager must review permissions."
    else:
        category = "UNCLASSIFIED"
        decision = "MANUAL_REVIEW"
        reason = "The failure cannot be safely classified for automatic retry."

    return {
        "failure_category": category,
        "recovery_decision": decision,
        "retry_allowed": False,
        "attempt_no": attempt_no,
        "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
        "side_effect_state": side_effect_state,
        "error_type": error_type,
        "error_message": message,
        "reason": reason,
    }


def request_manager_authorized_retry(
    db,
    action_id: int,
    manager,
) -> dict:
    """Create a fresh, approval-gated action after a safe transient failure.

    The failed action and its execution history are never reset or reused.
    A new plan/action is created, and a manager must approve it separately.
    """

    from sqlalchemy import func
    from app.models import (
        Action,
        ActionExecution,
        AgentRun,
        AuditLog,
        ResolutionPlan,
        Exception as ShipmentException,
    )
    from app.engines.resolution_planner import create_resolution_plan

    if manager is None or not getattr(manager, "is_active", False):
        raise PermissionError("An active manager account is required.")
    if getattr(manager, "role", None) not in {"ADMIN", "MANAGER"}:
        raise PermissionError("Only ADMIN and MANAGER users can request recovery.")

    action = (
        db.query(Action)
        .filter(Action.action_id == action_id)
        .with_for_update()
        .first()
    )
    if action is None:
        raise LookupError(f"Action {action_id} was not found.")
    if action.execution_status != "FAILED":
        raise ValueError("Only failed actions can enter recovery.")

    old_plan = (
        db.query(ResolutionPlan)
        .filter(ResolutionPlan.plan_id == action.plan_id)
        .with_for_update()
        .first()
    )
    if old_plan is None:
        raise LookupError("The failed action's resolution plan was not found.")

    exception = (
        db.query(ShipmentException)
        .filter(ShipmentException.exception_id == old_plan.exception_id)
        .with_for_update()
        .first()
    )
    if exception is None:
        raise LookupError("The exception associated with this action was not found.")
    if exception.status in {"RESOLVED", "CLOSED"}:
        raise ValueError("A resolved or closed exception cannot be retried.")

    latest_execution = (
        db.query(ActionExecution)
        .filter(ActionExecution.action_id == action_id)
        .order_by(ActionExecution.attempt_no.desc(), ActionExecution.execution_id.desc())
        .first()
    )
    if latest_execution is None or latest_execution.status != "FAILED":
        raise ValueError("A recorded failed execution attempt is required.")

    latest_run = (
        db.query(AgentRun)
        .filter(AgentRun.run_id == latest_execution.run_id)
        .first()
    )
    recovery_analysis = (
        (latest_run.output_data or {}).get("recovery_analysis")
        if latest_run else None
    )
    if not isinstance(recovery_analysis, dict):
        raise ValueError("No structured recovery assessment is available.")

    if recovery_analysis.get("recovery_decision") != "RETRY_CANDIDATE":
        raise ValueError(
            "This failure is not eligible for a retry. Manager/manual review is required."
        )
    if recovery_analysis.get("retry_allowed") is not True:
        raise ValueError("The recovery assessment does not permit retry.")
    if recovery_analysis.get("side_effect_state") != "NOT_COMMITTED":
        raise ValueError("Retry blocked because the operation's side-effect state is uncertain.")

    total_attempts = (
        db.query(func.count(ActionExecution.execution_id))
        .join(Action, Action.action_id == ActionExecution.action_id)
        .join(ResolutionPlan, ResolutionPlan.plan_id == Action.plan_id)
        .filter(ResolutionPlan.exception_id == exception.exception_id)
        .scalar()
        or 0
    )
    if total_attempts >= MAX_AUTOMATIC_ATTEMPTS:
        raise ValueError("The exception-level retry attempt limit has been reached.")

    # Capture scalar identifiers before releasing the read/row locks.
    exception_id = exception.exception_id
    shipment_id = exception.shipment_id
    workflow_id = action.workflow_id
    failed_action_id = action.action_id
    failed_plan_id = old_plan.plan_id
    manager_id = manager.user_id
    manager_name = manager.name

    # The existing deterministic planner creates a new action. No old action
    # or approval is reused, and the new action remains pending manager approval.
    db.rollback()
    proposal = create_resolution_plan(
        db=db,
        exception_id=exception_id,
        triggered_by=manager_id,
        decision_advisory=None,
    )

    new_plan = (
        db.query(ResolutionPlan)
        .filter(ResolutionPlan.plan_id == proposal["plan_id"])
        .with_for_update()
        .first()
    )
    if new_plan is None:
        raise RuntimeError("The replacement resolution plan could not be reloaded.")

    new_plan.supersedes_plan_id = failed_plan_id
    new_plan.reasoning = (
        (new_plan.reasoning or "")
        + "\n\nRECOVERY CONTEXT: This is a fresh, manager-requested "
        "proposal following a failed transient action. The previous action "
        f"was {action.action_id}; its execution history has been preserved. "
        "This replacement requires a separate human approval."
    )

    db.add(AuditLog(
        actor_type="USER",
        actor_user_id=manager_id,
        actor_name=manager_name,
        action="ACTION_RECOVERY_REQUESTED",
        entity_type="ACTION",
        entity_id=failed_action_id,
        shipment_id=shipment_id,
        workflow_id=workflow_id,
        details={
            "failed_action_id": failed_action_id,
            "failed_plan_id": failed_plan_id,
            "replacement_action_id": proposal["action_id"],
            "replacement_plan_id": proposal["plan_id"],
            "total_exception_attempts": total_attempts,
            "recovery_decision": recovery_analysis.get("recovery_decision"),
            "approval_required": True,
        },
    ))
    db.commit()

    proposal["supersedes_plan_id"] = failed_plan_id
    proposal["recovery_requested_by"] = manager_id
    proposal["approval_required"] = True
    return proposal
