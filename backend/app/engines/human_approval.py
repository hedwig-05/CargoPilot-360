
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Action,
    ResolutionPlan,
    AgentWorkflow,
    AuditLog,
    User
)
from app.engines.workflow_dependencies import (
    update_dependent_workflows
)

# ==================================================
# APPROVAL CONFIGURATION
# ==================================================

AUTHORIZED_APPROVERS = ("ADMIN", "MANAGER")


# ==================================================
# VALIDATE APPROVER
# ==================================================

def validate_approver(approver: User):
    """
    Verify that the user is active and authorized
    to approve or reject actions.
    """

    if approver is None:
        raise ValueError("Approver not found.")

    if not approver.is_active:
        raise ValueError("Inactive users cannot approve actions.")

    if approver.role not in AUTHORIZED_APPROVERS:
        raise PermissionError(
            "Only ADMIN and MANAGER users can approve or reject actions."
        )


# ==================================================
# LOAD AND VALIDATE ACTION
# ==================================================

def get_pending_action(db: Session, action_id: int):
    """
    Retrieve an action and its associated resolution
    plan and workflow.

    Lock the records to reduce the risk of simultaneous
    approval or rejection requests.
    """

    action = (
        db.query(Action)
        .filter(Action.action_id == action_id)
        .with_for_update()
        .first()
    )

    if action is None:
        raise LookupError(
            f"Action {action_id} was not found."
        )

    if not action.requires_approval:
        raise ValueError(
            "This action does not require approval."
        )

    if action.approval_status != "PENDING":
        raise ValueError(
            f"This action has already been processed. "
            f"Current approval status: {action.approval_status}."
        )

    plan = (
        db.query(ResolutionPlan)
        .filter(
            ResolutionPlan.plan_id == action.plan_id
        )
        .with_for_update()
        .first()
    )

    if plan is None:
        raise LookupError(
            "The resolution plan associated with this action was not found."
        )

    if plan.status != "PENDING_APPROVAL":
        raise ValueError(
            f"The resolution plan is not awaiting approval. "
            f"Current status: {plan.status}."
        )

    workflow = (
        db.query(AgentWorkflow)
        .filter(
            AgentWorkflow.workflow_id == action.workflow_id
        )
        .with_for_update()
        .first()
    )

    if workflow is None:
        raise LookupError(
            "The workflow associated with this action was not found."
        )

    if workflow.status != "WAITING_FOR_APPROVAL":
        raise ValueError(
            f"The workflow is not waiting for approval. "
            f"Current status: {workflow.status}."
        )

    return action, plan, workflow


# ==================================================
# CREATE AUDIT LOG
# ==================================================

def create_approval_audit_log(
    db: Session,
    action: Action,
    workflow: AgentWorkflow,
    approver: User,
    audit_action: str,
    details: dict
):
    """
    Record the approval or rejection decision.
    """

    audit_log = AuditLog(
        actor_type="USER",
        actor_user_id=approver.user_id,
        actor_name=approver.name,
        action=audit_action,
        entity_type="ACTION",
        entity_id=action.action_id,
        shipment_id=workflow.shipment_id,
        workflow_id=workflow.workflow_id,
        details=details
    )

    db.add(audit_log)


# ==================================================
# APPROVE ACTION
# ==================================================

def approve_action(
    db: Session,
    action_id: int,
    approver: User
):
    """
    Approve a pending action.

    This function does NOT execute the action.
    It only records approval and updates the
    associated resolution plan and workflow.
    """

    try:
        validate_approver(approver)

        action, plan, workflow = get_pending_action(
            db,
            action_id
        )

        current_time = datetime.now()

        # Update action
        action.approval_status = "APPROVED"
        action.approved_by = approver.user_id
        action.approved_at = current_time

        # Update resolution plan
        plan.status = "APPROVED"

        # Resume workflow
        workflow.status = "RUNNING"
        workflow.current_node = "ACTION_EXECUTION"
        workflow.completed_at = None

        # Notify workflows that depend on this action.
        dependent_count = update_dependent_workflows(
            db=db,
            parent_workflow_id=workflow.workflow_id,
            outcome="APPROVED",
            current_time=current_time
        )


        # Create audit record
        create_approval_audit_log(
            db=db,
            action=action,
            workflow=workflow,
            approver=approver,
            audit_action="ACTION_APPROVED",
            details={
                "decision": "APPROVED",
                "action_id": action.action_id,
                "plan_id": plan.plan_id,
                "approver_id": approver.user_id,
                "approver_role": approver.role,
                "approved_at": current_time.isoformat()
            }
        )

        db.commit()

        return {
            "message": "Action approved successfully.",
            "action_id": action.action_id,
            "plan_id": plan.plan_id,
            "workflow_id": workflow.workflow_id,
            "approval_status": action.approval_status,
            "plan_status": plan.status,
            "workflow_status": workflow.status,
            "approved_by": approver.user_id,
            "approved_at": current_time.isoformat()
        }

    except Exception:
        db.rollback()
        raise


# ==================================================
# REJECT ACTION
# ==================================================

def reject_action(
    db: Session,
    action_id: int,
    approver: User,
    rejection_reason: str
):
    """
    Reject a pending action.

    Rejection updates the action, resolution plan
    and workflow. It does NOT execute the action.
    """

    try:
        validate_approver(approver)

        if not rejection_reason or not rejection_reason.strip():
            raise ValueError(
                "A rejection reason must be provided."
            )

        action, plan, workflow = get_pending_action(
            db,
            action_id
        )

        current_time = datetime.now()

        # Update action
        action.approval_status = "REJECTED"
        action.rejection_reason = rejection_reason.strip()

        # Update resolution plan
        plan.status = "REJECTED"

        # End the workflow
        workflow.status = "COMPLETED"
        workflow.current_node = "REJECTED"
        workflow.completed_at = current_time

                # Notify dependent workflows about rejection.
        dependent_count = update_dependent_workflows(
            db=db,
            parent_workflow_id=workflow.workflow_id,
            outcome="REJECTED",
            current_time=current_time
        )
        # Create audit record
        create_approval_audit_log(
            db=db,
            action=action,
            workflow=workflow,
            approver=approver,
            audit_action="ACTION_REJECTED",
            details={
                "decision": "REJECTED",
                "action_id": action.action_id,
                "plan_id": plan.plan_id,
                "approver_id": approver.user_id,
                "approver_role": approver.role,
                "rejection_reason": rejection_reason.strip(),
                "rejected_at": current_time.isoformat()
            }
        )

        db.commit()

        return {
            "message": "Action rejected successfully.",
            "action_id": action.action_id,
            "plan_id": plan.plan_id,
            "workflow_id": workflow.workflow_id,
            "approval_status": action.approval_status,
            "plan_status": plan.status,
            "workflow_status": workflow.status,
            "rejection_reason": action.rejection_reason
        }

    except Exception:
        db.rollback()
        raise
