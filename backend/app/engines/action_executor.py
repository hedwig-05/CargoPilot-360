
import uuid
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Action,
    ActionExecution,
    AgentRun,
    AgentWorkflow,
    ResolutionPlan,
    Shipment,
    Exception as ShipmentException,
    AuditLog
)


# ==================================================
# CONFIGURATION
# ==================================================

SUPPORTED_ACTION_TYPES = {
    "REQUEST_DOCUMENT_CORRECTION",
    "REQUEST_MISSING_DOCUMENT",
    "SEND_FOLLOW_UP_EMAIL",
    "NOTIFY_OPERATIONS_OFFICER",
    "ESCALATE_TO_MANAGER",
    "UPDATE_SHIPMENT_STATUS",
    "CREATE_NOTIFICATION"
}


VALID_SHIPMENT_STATUSES = {
    "BOOKED",
    "DOCUMENTATION",
    "IN_TRANSIT",
    "ARRIVED",
    "CUSTOMS",
    "DELIVERED",
    "ON_HOLD",
    "CANCELLED"
}


ACTION_MESSAGES = {
    "REQUEST_DOCUMENT_CORRECTION":
        "A document correction request has been prepared.",

    "REQUEST_MISSING_DOCUMENT":
        "A missing document request has been prepared.",

    "SEND_FOLLOW_UP_EMAIL":
        "A stakeholder follow-up email has been prepared.",

    "NOTIFY_OPERATIONS_OFFICER":
        "An operations officer notification has been prepared.",

    "ESCALATE_TO_MANAGER":
        "A managerial escalation has been prepared.",

    "UPDATE_SHIPMENT_STATUS":
        "The shipment status has been updated.",

    "CREATE_NOTIFICATION":
        "An internal notification has been created."
}


# ==================================================
# GET AND VALIDATE ACTION
# ==================================================

def get_action_for_execution(
    db: Session,
    action_id: int
):

    action = (
        db.query(Action)
        .filter(Action.action_id == action_id)
        .with_for_update()
        .first()
    )

    if not action:

        raise LookupError(
            f"Action {action_id} not found."
        )

    # ------------------------------------------
    # CHECK APPROVAL
    # ------------------------------------------

    if action.requires_approval:

        if action.approval_status != "APPROVED":

            raise ValueError(
                "Action must be approved before execution."
            )

    elif action.approval_status != "NOT_REQUIRED":

        raise ValueError(
            "Action approval configuration is inconsistent."
        )

    # ------------------------------------------
    # CHECK EXECUTION STATUS
    # ------------------------------------------

    if action.execution_status in [
        "EXECUTING",
        "SUCCEEDED",
        "SKIPPED"
    ]:

        raise ValueError(
            f"Action cannot be executed. "
            f"Current status: {action.execution_status}"
        )

    if action.execution_status != "NOT_STARTED":

        raise ValueError(
            f"Action cannot be executed. "
            f"Current status: {action.execution_status}"
        )

    # ------------------------------------------
    # CHECK ACTION TYPE
    # ------------------------------------------

    if action.action_type not in SUPPORTED_ACTION_TYPES:

        raise ValueError(
            f"Unsupported action type: {action.action_type}"
        )

    return action


# ==================================================
# GET AND VALIDATE WORKFLOW
# ==================================================

def get_workflow_for_execution(
    db: Session,
    action: Action
):

    workflow = (
        db.query(AgentWorkflow)
        .filter(
            AgentWorkflow.workflow_id == action.workflow_id
        )
        .with_for_update()
        .first()
    )

    if not workflow:

        raise LookupError(
            f"Workflow {action.workflow_id} not found."
        )

    if workflow.status != "RUNNING":

        raise ValueError(
            f"Workflow is not ready for execution. "
            f"Current status: {workflow.status}"
        )

    if workflow.current_node != "ACTION_EXECUTION":

        raise ValueError(
            "Workflow is not at the ACTION_EXECUTION node."
        )

    return workflow


# ==================================================
# GET AND VALIDATE RESOLUTION PLAN
# ==================================================

def get_plan_for_execution(
    db: Session,
    action: Action
):

    plan = (
        db.query(ResolutionPlan)
        .filter(
            ResolutionPlan.plan_id == action.plan_id,
            ResolutionPlan.workflow_id == action.workflow_id
        )
        .with_for_update()
        .first()
    )

    if not plan:

        raise LookupError(
            f"Resolution plan {action.plan_id} not found."
        )

    if action.requires_approval:

        if plan.status != "APPROVED":

            raise ValueError(
                "Resolution plan must be approved before execution."
            )

    return plan


# ==================================================
# GET SHIPMENT AND EXCEPTION CONTEXT
# ==================================================

def get_execution_context(
    db: Session,
    action: Action,
    workflow: AgentWorkflow,
    plan: ResolutionPlan
):

    # ------------------------------------------
    # GET SHIPMENT
    # ------------------------------------------

    shipment = (
        db.query(Shipment)
        .filter(
            Shipment.shipment_id == workflow.shipment_id
        )
        .with_for_update()
        .first()
    )

    if not shipment:

        raise LookupError(
            f"Shipment {workflow.shipment_id} not found."
        )

    # ------------------------------------------
    # GET EXCEPTION
    # ------------------------------------------

    exception = None

    if plan.exception_id is not None:

        exception = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.exception_id == plan.exception_id
            )
            .with_for_update()
            .first()
        )

        if not exception:

            raise LookupError(
                f"Exception {plan.exception_id} not found."
            )

        if exception.shipment_id != shipment.shipment_id:

            raise ValueError(
                "Exception and shipment do not belong together."
            )

    return shipment, exception


# ==================================================
# EXECUTE SIMULATED ACTION
# ==================================================

def execute_simulated_action(
    action: Action,
    shipment: Shipment,
    exception: ShipmentException
):

    action_type = action.action_type

    payload = action.action_payload or {}

    # ------------------------------------------
    # REQUEST DOCUMENT CORRECTION
    # ------------------------------------------

    if action_type == "REQUEST_DOCUMENT_CORRECTION":

        return {
            "operation": "DOCUMENT_CORRECTION_REQUEST",
            "shipment_ref": shipment.shipment_ref,
            "exception_id": exception.exception_id if exception else None,
            "message": ACTION_MESSAGES[action_type],
            "simulation": True
        }

    # ------------------------------------------
    # REQUEST MISSING DOCUMENT
    # ------------------------------------------

    if action_type == "REQUEST_MISSING_DOCUMENT":

        return {
            "operation": "MISSING_DOCUMENT_REQUEST",
            "shipment_ref": shipment.shipment_ref,
            "exception_id": exception.exception_id if exception else None,
            "message": ACTION_MESSAGES[action_type],
            "simulation": True
        }

    # ------------------------------------------
    # SEND FOLLOW-UP EMAIL
    # ------------------------------------------

    if action_type == "SEND_FOLLOW_UP_EMAIL":

        return {
            "operation": "FOLLOW_UP_EMAIL_REQUEST",
            "shipment_ref": shipment.shipment_ref,
            "recipient": payload.get("recipient"),
            "message": ACTION_MESSAGES[action_type],
            "email_sent": False,
            "simulation": True
        }

    # ------------------------------------------
    # NOTIFY OPERATIONS OFFICER
    # ------------------------------------------

    if action_type == "NOTIFY_OPERATIONS_OFFICER":

        return {
            "operation": "OPERATIONS_NOTIFICATION",
            "shipment_ref": shipment.shipment_ref,
            "assigned_user_id": shipment.assigned_user_id,
            "message": ACTION_MESSAGES[action_type],
            "notification_sent": False,
            "simulation": True
        }

    # ------------------------------------------
    # ESCALATE TO MANAGER
    # ------------------------------------------

    if action_type == "ESCALATE_TO_MANAGER":

        return {
            "operation": "MANAGERIAL_ESCALATION",
            "shipment_ref": shipment.shipment_ref,
            "exception_id": exception.exception_id if exception else None,
            "priority": action_payload_priority(action),
            "message": ACTION_MESSAGES[action_type],
            "escalation_sent": False,
            "simulation": True
        }

    # ------------------------------------------
    # UPDATE SHIPMENT STATUS
    # ------------------------------------------

    if action_type == "UPDATE_SHIPMENT_STATUS":

        new_status = payload.get("new_status")

        if new_status not in VALID_SHIPMENT_STATUSES:

            raise ValueError(
                "A valid new_status must be supplied in action_payload."
            )

        previous_status = shipment.status

        shipment.status = new_status

        return {
            "operation": "SHIPMENT_STATUS_UPDATE",
            "shipment_ref": shipment.shipment_ref,
            "previous_status": previous_status,
            "new_status": new_status,
            "message": ACTION_MESSAGES[action_type],
            "simulation": True
        }

    # ------------------------------------------
    # CREATE NOTIFICATION
    # ------------------------------------------

    if action_type == "CREATE_NOTIFICATION":

        return {
            "operation": "INTERNAL_NOTIFICATION",
            "shipment_ref": shipment.shipment_ref,
            "exception_id": exception.exception_id if exception else None,
            "message": ACTION_MESSAGES[action_type],
            "notification_sent": False,
            "simulation": True
        }

    raise ValueError(
        f"Unsupported action type: {action_type}"
    )


# ==================================================
# GET ACTION PRIORITY
# ==================================================

def action_payload_priority(action: Action):

    return (action.action_payload or {}).get(
        "priority",
        "NORMAL"
    )


# ==================================================
# CREATE ACTION AGENT RUN
# ==================================================

def create_action_agent_run(
    db: Session,
    action: Action,
    workflow: AgentWorkflow
):

    # Get the latest step number for this workflow.

    latest_run = (
        db.query(AgentRun)
        .filter(
            AgentRun.workflow_id == workflow.workflow_id
        )
        .order_by(
            AgentRun.step_no.desc()
        )
        .first()
    )

    next_step_no = (
        latest_run.step_no + 1
        if latest_run else 1
    )

    run = AgentRun(
        run_public_id=(
            f"RUN-{uuid.uuid4().hex[:12].upper()}"
        ),

        workflow_id=workflow.workflow_id,

        parent_run_id=action.created_by_run_id,

        step_no=next_step_no,

        agent_type="ACTION",

        node_name="action_executor",

        input_data={
            "action_id": action.action_id,
            "action_type": action.action_type,
            "plan_id": action.plan_id,
            "shipment_id": workflow.shipment_id
        },

        execution_status="PROCESSING"
    )

    db.add(run)
    db.flush()

    return run


# ==================================================
# CREATE ACTION EXECUTION ATTEMPT
# ==================================================

def create_action_execution(
    db: Session,
    action: Action,
    workflow: AgentWorkflow,
    run: AgentRun
):

    # Get the latest attempt number for this action.

    latest_execution = (
        db.query(ActionExecution)
        .filter(
            ActionExecution.action_id == action.action_id
        )
        .order_by(
            ActionExecution.attempt_no.desc()
        )
        .first()
    )

    next_attempt_no = (
        latest_execution.attempt_no + 1
        if latest_execution else 1
    )

    execution = ActionExecution(
        action_id=action.action_id,

        workflow_id=workflow.workflow_id,

        run_id=run.run_id,

        attempt_no=next_attempt_no,

        status="STARTED",

        request_data={
            "action_id": action.action_id,
            "action_type": action.action_type,
            "action_payload": action.action_payload
        }
    )

    db.add(execution)
    db.flush()

    return execution


# ==================================================
# CREATE ACTION EXECUTION AUDIT LOG
# ==================================================

def create_execution_audit_log(
    db: Session,
    action: Action,
    workflow: AgentWorkflow,
    run: AgentRun,
    execution: ActionExecution,
    result: dict,
    audit_action: str
):

    audit_log = AuditLog(
        actor_type="AGENT",

        actor_user_id=None,

        actor_name="CargoPilot Action Executor",

        action=audit_action,

        entity_type="ACTION",

        entity_id=action.action_id,

        shipment_id=workflow.shipment_id,

        workflow_id=workflow.workflow_id,

        run_id=run.run_id,

        details={
            "action_id": action.action_id,
            "action_type": action.action_type,
            "execution_id": execution.execution_id,
            "attempt_no": execution.attempt_no,
            "execution_status": execution.status,
            "result": result
        }
    )

    db.add(audit_log)

    db.flush()

    return audit_log


# ==================================================
# MAIN ACTION EXECUTION CONTROLLER
# ==================================================

def execute_action(
    db: Session,
    action_id: int
):

    started_at = time.perf_counter()

    try:

        # ------------------------------------------
        # 1. GET AND VALIDATE ACTION
        # ------------------------------------------

        action = get_action_for_execution(
            db=db,
            action_id=action_id
        )

        # ------------------------------------------
        # 2. GET WORKFLOW
        # ------------------------------------------

        workflow = get_workflow_for_execution(
            db=db,
            action=action
        )

        # ------------------------------------------
        # 3. GET RESOLUTION PLAN
        # ------------------------------------------

        plan = get_plan_for_execution(
            db=db,
            action=action
        )

        # ------------------------------------------
        # 4. GET SHIPMENT AND EXCEPTION
        # ------------------------------------------

        shipment, exception = get_execution_context(
            db=db,
            action=action,
            workflow=workflow,
            plan=plan
        )

        # ------------------------------------------
        # 5. CREATE ACTION AGENT RUN
        # ------------------------------------------

        run = create_action_agent_run(
            db=db,
            action=action,
            workflow=workflow
        )

        # ------------------------------------------
        # 6. CREATE EXECUTION ATTEMPT
        # ------------------------------------------

        execution = create_action_execution(
            db=db,
            action=action,
            workflow=workflow,
            run=run
        )

        # Save IDs for failure handling.

        execution_id = execution.execution_id
        run_id = run.run_id

        # ------------------------------------------
        # 7. UPDATE EXECUTION STATE
        # ------------------------------------------

        action.execution_status = "EXECUTING"

        plan.status = "EXECUTING"

        workflow.status = "RUNNING"

        workflow.current_node = "ACTION_EXECUTION"

        if exception and exception.status not in [
            "RESOLVED",
            "CLOSED"
        ]:

            exception.status = "IN_PROGRESS"

        # Save the STARTED execution records.

        db.commit()

        db.refresh(action)
        db.refresh(execution)
        db.refresh(run)

        # ------------------------------------------
        # 8. EXECUTE SIMULATED OPERATION
        # ------------------------------------------

        try:

            result = execute_simulated_action(
                action=action,
                shipment=shipment,
                exception=exception
            )

            completed_at = datetime.now()

            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            # --------------------------------------
            # 9. UPDATE SUCCESSFUL EXECUTION
            # --------------------------------------

            execution.status = "SUCCEEDED"

            execution.response_data = result

            execution.completed_at = completed_at

            action.execution_status = "SUCCEEDED"

            action.executed_at = completed_at

            plan.status = "COMPLETED"

            workflow.status = "COMPLETED"

            workflow.current_node = "ACTION_COMPLETED"

            workflow.completed_at = completed_at

            run.execution_status = "COMPLETED"

            run.output_data = {
                "execution_id": execution.execution_id,
                "action_id": action.action_id,
                "result": result
            }

            run.latency_ms = latency_ms

            run.completed_at = completed_at

            # --------------------------------------
            # 10. CREATE SUCCESS AUDIT LOG
            # --------------------------------------

            create_execution_audit_log(
                db=db,
                action=action,
                workflow=workflow,
                run=run,
                execution=execution,
                result=result,
                audit_action="ACTION_EXECUTED"
            )

            db.commit()

            return {
                "success": True,
                "message": "Action executed successfully.",
                "action_id": action.action_id,
                "execution_id": execution.execution_id,
                "run_id": run.run_id,
                "attempt_no": execution.attempt_no,
                "action_type": action.action_type,
                "execution_status": action.execution_status,
                "plan_status": plan.status,
                "workflow_status": workflow.status,
                "result": result
            }

        except Exception as error:

            # --------------------------------------
            # 11. RECORD EXECUTION FAILURE
            # --------------------------------------

            # IDs were saved before the transaction
            # rollback because SQLAlchemy may expire
            # objects after rollback.

            db.rollback()

            # Reload records after rollback.

            action = (
                db.query(Action)
                .filter(
                    Action.action_id == action_id
                )
                .with_for_update()
                .first()
            )

            execution = (
                db.query(ActionExecution)
                .filter(
                    ActionExecution.execution_id == execution_id
                )
                .with_for_update()
                .first()
            )

            run = (
                db.query(AgentRun)
                .filter(
                    AgentRun.run_id == run_id
                )
                .with_for_update()
                .first()
            )

            workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_id == action.workflow_id
                )
                .with_for_update()
                .first()
            )

            plan = (
                db.query(ResolutionPlan)
                .filter(
                    ResolutionPlan.plan_id == action.plan_id
                )
                .with_for_update()
                .first()
            )

            if not all([
                action,
                execution,
                run,
                workflow,
                plan
            ]):

                raise RuntimeError(
                    "Could not reload all records after execution failure."
                )

            completed_at = datetime.now()

            error_message = str(error)

            execution.status = "FAILED"

            execution.error_message = error_message

            execution.completed_at = completed_at

            action.execution_status = "FAILED"

            plan.status = "FAILED"

            workflow.status = "FAILED"

            workflow.current_node = "ACTION_FAILED"

            workflow.error_message = error_message

            workflow.completed_at = completed_at

            run.execution_status = "FAILED"

            run.error_message = error_message

            run.output_data = {
                "execution_id": execution.execution_id,
                "action_id": action.action_id,
                "error": error_message
            }

            run.latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            run.completed_at = completed_at

            create_execution_audit_log(
                db=db,
                action=action,
                workflow=workflow,
                run=run,
                execution=execution,
                result={
                    "error": error_message
                },
                audit_action="ACTION_EXECUTION_FAILED"
            )

            db.commit()

            return {
                "success": False,
                "message": "Action execution failed.",
                "action_id": action.action_id,
                "execution_id": execution.execution_id,
                "run_id": run.run_id,
                "attempt_no": execution.attempt_no,
                "execution_status": action.execution_status,
                "error": error_message
            }

    except Exception:

        db.rollback()
        raise
