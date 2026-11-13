
import uuid
import time

from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.models import (
    Shipment,
    Document,
    AgentWorkflow,
    AgentRun,
    Exception as ShipmentException,
    ResolutionPlan,
    Action
)

from app.engines.document_processing import process_document
from app.engines.document_validation import validate_shipment_documents
from app.engines.investigation import investigate_exception
from app.engines.risk_assessment import assess_shipment_risk
from app.engines.resolution_planner import create_resolution_plan
from app.engines.action_executor import execute_action
from app.engines.resolution_verification import verify_exception_resolution


# ======================================================
# COMMON HELPERS
# ======================================================

ACTIVE_PLAN_STATUSES = [
    "DRAFT",
    "PENDING_APPROVAL",
    "APPROVED",
    "EXECUTING"
]


def make_json_safe(value):
    """Convert Python values into JSON-compatible values."""

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            make_json_safe(item)
            for item in value
        ]

    if value is None or isinstance(
        value,
        (str, int, float, bool)
    ):
        return value

    return str(value)


def generate_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def create_agent_run(
    db,
    workflow,
    parent_run_id,
    step_no,
    agent_type,
    node_name,
    input_data
):

    run = AgentRun(
        run_public_id=generate_id("RUN"),
        workflow_id=workflow.workflow_id,
        parent_run_id=parent_run_id,
        step_no=step_no,
        agent_type=agent_type,
        node_name=node_name,
        input_data=make_json_safe(input_data),
        execution_status="PROCESSING"
    )

    db.add(run)
    db.flush()

    return run


def complete_agent_run(db, run, output_data):

    run.output_data = make_json_safe(output_data)
    run.execution_status = "COMPLETED"
    run.completed_at = datetime.now()

    db.flush()


def fail_agent_run(db, run, error):

    run.execution_status = "FAILED"
    run.error_message = str(error)
    run.completed_at = datetime.now()

    db.flush()


def get_active_resolution_plan(db, exception_id):
    """
    Return an existing active resolution plan.

    This prevents duplicate plans for the same exception.
    """

    return (
        db.query(ResolutionPlan)
        .filter(
            ResolutionPlan.exception_id == exception_id,
            ResolutionPlan.status.in_(ACTIVE_PLAN_STATUSES)
        )
        .order_by(
            ResolutionPlan.plan_id.desc()
        )
        .first()
    )


def link_action_to_supervisor(
    db,
    action,
    supervisor_workflow_id,
    supervisor_run_id,
    exception_workflow_id
):
    """
    Store the Supervisor references in the action payload.

    This allows continue_supervisor() to update the
    correct parent Supervisor workflow after approval.
    """

    payload = dict(action.action_payload or {})

    payload["supervisor_workflow_id"] = supervisor_workflow_id
    payload["supervisor_run_id"] = supervisor_run_id
    payload["exception_workflow_id"] = exception_workflow_id

    action.action_payload = payload

    db.flush()


# ======================================================
# EXCEPTION-SPECIFIC WORKFLOW
# ======================================================

def create_exception_workflow(
    db,
    shipment_id,
    exception_id,
    triggered_by=None
):
    """
    Create a workflow for an individual exception.

    exception_id must be populated because the
    investigations table uses a composite foreign key.
    """

    workflow = AgentWorkflow(
        workflow_public_id=generate_id("WF"),
        thread_id=generate_id("THREAD"),
        shipment_id=shipment_id,
        exception_id=exception_id,
        trigger_type="MANUAL",
        trigger_ref=f"SUPERVISOR_EXCEPTION_{exception_id}",
        graph_name="cargopilot_main",
        status="RUNNING",
        current_node="INVESTIGATION",
        triggered_by=triggered_by
    )

    db.add(workflow)
    db.flush()

    return workflow


# ======================================================
# SUPERVISOR AGENT
# ======================================================

def run_supervisor(
    db: Session,
    shipment_id: int,
    triggered_by: int = None
):

    started_at = time.perf_counter()

    # --------------------------------------------------
    # 1. FIND SHIPMENT
    # --------------------------------------------------

    shipment = (
        db.query(Shipment)
        .filter(
            Shipment.shipment_id == shipment_id
        )
        .first()
    )

    if shipment is None:
        raise ValueError(
            f"Shipment {shipment_id} was not found."
        )

    if shipment.status in ["CANCELLED", "DELIVERED"]:
        raise ValueError(
            "Supervisor cannot process a cancelled or delivered shipment."
        )

    shipment_ref = shipment.shipment_ref

    # --------------------------------------------------
    # 2. CREATE SUPERVISOR WORKFLOW
    # --------------------------------------------------

    workflow = AgentWorkflow(
        workflow_public_id=generate_id("WF"),
        thread_id=generate_id("THREAD"),
        shipment_id=shipment_id,
        trigger_type="MANUAL",
        trigger_ref=f"SUPERVISOR_SHIPMENT_{shipment_id}",
        graph_name="cargopilot_main",
        status="RUNNING",
        current_node="SUPERVISOR",
        triggered_by=triggered_by
    )

    db.add(workflow)
    db.flush()

    workflow_id = workflow.workflow_id

    # --------------------------------------------------
    # 3. CREATE SUPERVISOR AGENT RUN
    # --------------------------------------------------

    supervisor_run = create_agent_run(
        db=db,
        workflow=workflow,
        parent_run_id=None,
        step_no=1,
        agent_type="SUPERVISOR",
        node_name="supervisor",
        input_data={
            "shipment_id": shipment_id,
            "shipment_ref": shipment_ref,
            "trigger": "MANUAL"
        }
    )

    supervisor_run_id = supervisor_run.run_id

    db.commit()

    results = {
        "shipment_id": shipment_id,
        "shipment_ref": shipment_ref,
        "workflow_id": workflow_id,
        "supervisor_run_id": supervisor_run_id,
        "document_processing": [],
        "document_validation": None,
        "exceptions_found": [],
        "exception_workflows": [],
        "investigations": [],
        "risk_assessments": [],
        "resolution_plans": [],
        "warnings": [],
        "errors": []
    }

    step_no = 2

    try:

        # --------------------------------------------------
        # 4. DOCUMENT PROCESSING
        # --------------------------------------------------

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        workflow.current_node = "DOCUMENT_PROCESSING"

        document_run = create_agent_run(
            db,
            workflow,
            supervisor_run_id,
            step_no,
            "DOCUMENT",
            "document_processing",
            {
                "shipment_id": shipment_id
            }
        )

        document_run_id = document_run.run_id

        db.commit()

        documents = (
            db.query(Document)
            .filter(
                Document.shipment_id == shipment_id
            )
            .order_by(
                Document.version_no.desc(),
                Document.document_id.desc()
            )
            .all()
        )

        document_ids = [
            document.document_id
            for document in documents
        ]

        processed_documents = []

        for document_id in document_ids:

            try:

                document = (
                    db.query(Document)
                    .filter(
                        Document.document_id == document_id
                    )
                    .first()
                )

                if document is None:
                    continue

                if document.extraction_status != "EXTRACTED":

                    process_document(
                        db=db,
                        document_id=document_id
                    )

                    db.commit()

                    document = (
                        db.query(Document)
                        .filter(
                            Document.document_id == document_id
                        )
                        .first()
                    )

                    processed_documents.append({
                        "document_id": document_id,
                        "extraction_status": (
                            document.extraction_status
                            if document else "UNKNOWN"
                        )
                    })

                else:

                    processed_documents.append({
                        "document_id": document_id,
                        "status": "ALREADY_EXTRACTED"
                    })

            except Exception as error:

                db.rollback()

                results["errors"].append({
                    "stage": "DOCUMENT_PROCESSING",
                    "document_id": document_id,
                    "error": str(error)
                })

        document_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.run_id == document_run_id
            )
            .first()
        )

        if document_run:

            complete_agent_run(
                db,
                document_run,
                {
                    "documents_found": len(document_ids),
                    "documents_processed": processed_documents
                }
            )

        results["document_processing"] = processed_documents

        db.commit()

        step_no += 1

        # --------------------------------------------------
        # 5. DOCUMENT VALIDATION
        # --------------------------------------------------

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        workflow.current_node = "DOCUMENT_VALIDATION"

        validation_run = create_agent_run(
            db,
            workflow,
            supervisor_run_id,
            step_no,
            "DOCUMENT",
            "document_validation",
            {
                "shipment_id": shipment_id
            }
        )

        validation_run_id = validation_run.run_id

        db.commit()

        try:

            validation_result = validate_shipment_documents(
                db=db,
                shipment_id=shipment_id,
                commit=True
            )

            results["document_validation"] = validation_result

            validation_run = (
                db.query(AgentRun)
                .filter(
                    AgentRun.run_id == validation_run_id
                )
                .first()
            )

            if validation_run:

                complete_agent_run(
                    db,
                    validation_run,
                    validation_result
                )

        except Exception as error:

            db.rollback()

            error_message = str(error)

            validation_run = (
                db.query(AgentRun)
                .filter(
                    AgentRun.run_id == validation_run_id
                )
                .first()
            )

            if validation_run:

                validation_run.execution_status = "SKIPPED"
                validation_run.error_message = error_message
                validation_run.completed_at = datetime.now()

            if (
                "Both Commercial Invoice and Bill of Lading are required"
                in error_message
            ):

                results["warnings"].append({
                    "stage": "DOCUMENT_VALIDATION",
                    "message": error_message,
                    "reason": "REQUIRED_DOCUMENT_MISSING"
                })

                results["document_validation"] = {
                    "status": "SKIPPED",
                    "reason": "REQUIRED_DOCUMENT_MISSING",
                    "message": error_message
                }

            else:

                results["errors"].append({
                    "stage": "DOCUMENT_VALIDATION",
                    "error": error_message
                })

        db.commit()

        step_no += 1

        # --------------------------------------------------
        # 6. FIND ACTIVE EXCEPTIONS
        # --------------------------------------------------

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        workflow.current_node = "EXCEPTION_DETECTION"

        exceptions = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.shipment_id == shipment_id,
                ShipmentException.status.notin_([
                    "RESOLVED",
                    "CLOSED"
                ])
            )
            .order_by(
                ShipmentException.exception_id.asc()
            )
            .all()
        )

        results["exceptions_found"] = [
            {
                "exception_id": exception.exception_id,
                "exception_type": exception.exception_type,
                "severity": exception.severity,
                "status": exception.status
            }
            for exception in exceptions
        ]

        # --------------------------------------------------
        # 7. PROCESS EACH EXCEPTION
        # --------------------------------------------------

        for exception in exceptions:

            exception_id = exception.exception_id

            # ----------------------------------------------
            # 7A. CHECK FOR EXISTING ACTIVE PLAN
            # ----------------------------------------------

            existing_plan = get_active_resolution_plan(
                db,
                exception_id
            )

            if existing_plan:

                existing_action = (
                    db.query(Action)
                    .filter(
                        Action.plan_id == existing_plan.plan_id
                    )
                    .first()
                )

                # Reuse the workflow associated with the plan.
                existing_child_workflow_id = existing_plan.workflow_id

                if existing_action:

                    link_action_to_supervisor(
                        db=db,
                        action=existing_action,
                        supervisor_workflow_id=workflow_id,
                        supervisor_run_id=supervisor_run_id,
                        exception_workflow_id=existing_child_workflow_id
                    )

                db.commit()

                results["resolution_plans"].append({
                    "message": "An active resolution plan already exists. Reusing it.",
                    "exception_id": exception_id,
                    "workflow_id": existing_plan.workflow_id,
                    "plan_id": existing_plan.plan_id,
                    "action_id": (
                        existing_action.action_id
                        if existing_action else None
                    ),
                    "priority": existing_plan.priority,
                    "plan_status": existing_plan.status,
                    "approval_status": (
                        existing_action.approval_status
                        if existing_action else None
                    ),
                    "execution_status": (
                        existing_action.execution_status
                        if existing_action else None
                    ),
                    "existing_plan": True
                })

                results["warnings"].append({
                    "stage": "RESOLUTION_PLANNING",
                    "exception_id": exception_id,
                    "message": (
                        f"Existing active plan {existing_plan.plan_id} "
                        "was reused. No duplicate plan was created."
                    )
                })

                continue

            # ----------------------------------------------
            # 7B. CREATE EXCEPTION-SPECIFIC WORKFLOW
            # ----------------------------------------------

            child_workflow = create_exception_workflow(
                db=db,
                shipment_id=shipment_id,
                exception_id=exception_id,
                triggered_by=triggered_by
            )

            child_workflow_id = child_workflow.workflow_id

            db.commit()

            results["exception_workflows"].append({
                "exception_id": exception_id,
                "workflow_id": child_workflow_id,
                "parent_workflow_id": workflow_id
            })

            # ----------------------------------------------
            # 7C. INVESTIGATION AGENT
            # ----------------------------------------------

            child_workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_id == child_workflow_id
                )
                .first()
            )

            child_workflow.current_node = "INVESTIGATION"

            investigation_run = create_agent_run(
                db,
                child_workflow,
                None,
                step_no,
                "INVESTIGATION",
                "investigation",
                {
                    "shipment_id": shipment_id,
                    "exception_id": exception_id,
                    "supervisor_workflow_id": workflow_id,
                    "supervisor_run_id": supervisor_run_id
                }
            )

            investigation_run_id = investigation_run.run_id

            db.commit()

            try:

                investigation_result = investigate_exception(
                    db=db,
                    exception_id=exception_id,
                    workflow_id=child_workflow_id,
                    run_id=investigation_run_id,
                    commit=True
                )

                investigation_run = (
                    db.query(AgentRun)
                    .filter(
                        AgentRun.run_id == investigation_run_id
                    )
                    .first()
                )

                if investigation_run:

                    complete_agent_run(
                        db,
                        investigation_run,
                        investigation_result
                    )

                db.commit()

                results["investigations"].append(
                    investigation_result
                )

            except Exception as error:

                db.rollback()

                results["errors"].append({
                    "stage": "INVESTIGATION",
                    "exception_id": exception_id,
                    "error": str(error)
                })

                child_workflow = (
                    db.query(AgentWorkflow)
                    .filter(
                        AgentWorkflow.workflow_id == child_workflow_id
                    )
                    .first()
                )

                if child_workflow:

                    child_workflow.status = "FAILED"
                    child_workflow.current_node = "INVESTIGATION_FAILED"
                    child_workflow.error_message = str(error)
                    child_workflow.completed_at = datetime.now()

                    db.commit()

                continue

            step_no += 1

            # ----------------------------------------------
            # 7D. RISK ASSESSMENT AGENT
            # ----------------------------------------------

            child_workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_id == child_workflow_id
                )
                .first()
            )

            child_workflow.current_node = "RISK_ASSESSMENT"

            risk_run = create_agent_run(
                db,
                child_workflow,
                investigation_run_id,
                step_no,
                "DECISION",
                "risk_assessment",
                {
                    "shipment_id": shipment_id,
                    "exception_id": exception_id
                }
            )

            risk_run_id = risk_run.run_id

            db.commit()

            try:

                risk_result = assess_shipment_risk(
                    db=db,
                    shipment_id=shipment_id,
                    exception_id=exception_id,
                    workflow_id=child_workflow_id,
                    run_id=risk_run_id
                )

                risk_run = (
                    db.query(AgentRun)
                    .filter(
                        AgentRun.run_id == risk_run_id
                    )
                    .first()
                )

                if risk_run:

                    complete_agent_run(
                        db,
                        risk_run,
                        {
                            "risk_id": risk_result.get("risk_id"),
                            "shipment_id": shipment_id,
                            "risk_score": risk_result.get("risk_score"),
                            "risk_level": risk_result.get("risk_level"),
                            "explanation": risk_result.get("explanation")
                        }
                    )

                db.commit()

                results["risk_assessments"].append(
                    risk_result
                )

            except Exception as error:

                db.rollback()

                results["errors"].append({
                    "stage": "RISK_ASSESSMENT",
                    "exception_id": exception_id,
                    "error": str(error)
                })

                child_workflow = (
                    db.query(AgentWorkflow)
                    .filter(
                        AgentWorkflow.workflow_id == child_workflow_id
                    )
                    .first()
                )

                if child_workflow:

                    child_workflow.status = "FAILED"
                    child_workflow.current_node = "RISK_ASSESSMENT_FAILED"
                    child_workflow.error_message = str(error)
                    child_workflow.completed_at = datetime.now()

                    db.commit()

                continue

            step_no += 1

            # ----------------------------------------------
            # 7E. DECISION / RESOLUTION PLANNING
            # ----------------------------------------------

            child_workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_id == child_workflow_id
                )
                .first()
            )

            child_workflow.current_node = "DECISION"

            try:

                plan_result = create_resolution_plan(
                    db=db,
                    exception_id=exception_id,
                    triggered_by=triggered_by
                )

                action = (
                    db.query(Action)
                    .filter(
                        Action.action_id == plan_result["action_id"]
                    )
                    .first()
                )

                if action:

                    link_action_to_supervisor(
                        db=db,
                        action=action,
                        supervisor_workflow_id=workflow_id,
                        supervisor_run_id=supervisor_run_id,
                        exception_workflow_id=child_workflow_id
                    )

                db.commit()

                plan_result["existing_plan"] = False

                results["resolution_plans"].append(
                    plan_result
                )

                child_workflow = (
                    db.query(AgentWorkflow)
                    .filter(
                        AgentWorkflow.workflow_id == child_workflow_id
                    )
                    .first()
                )

                if child_workflow:

                    child_workflow.status = "WAITING_FOR_APPROVAL"
                    child_workflow.current_node = "WAITING_FOR_APPROVAL"

                    db.commit()

            except Exception as error:

                db.rollback()

                results["errors"].append({
                    "stage": "RESOLUTION_PLANNING",
                    "exception_id": exception_id,
                    "error": str(error)
                })

                child_workflow = (
                    db.query(AgentWorkflow)
                    .filter(
                        AgentWorkflow.workflow_id == child_workflow_id
                    )
                    .first()
                )

                if child_workflow:

                    child_workflow.status = "FAILED"
                    child_workflow.current_node = "RESOLUTION_PLANNING_FAILED"
                    child_workflow.error_message = str(error)
                    child_workflow.completed_at = datetime.now()

                    db.commit()

                continue

            step_no += 1

        # --------------------------------------------------
        # 8. FINAL SUPERVISOR STATUS
        # --------------------------------------------------

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        supervisor_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.run_id == supervisor_run_id
            )
            .first()
        )

        completed_at = datetime.now()

        if results["resolution_plans"]:

            workflow.status = "WAITING_FOR_APPROVAL"
            workflow.current_node = "WAITING_FOR_APPROVAL"

            supervisor_run.execution_status = "WAITING_FOR_APPROVAL"

        elif results["errors"]:

            workflow.status = "FAILED"
            workflow.current_node = "SUPERVISOR_COMPLETED_WITH_ERRORS"

            supervisor_run.execution_status = "FAILED"

        else:

            workflow.status = "COMPLETED"
            workflow.current_node = "SUPERVISOR_COMPLETED"
            workflow.completed_at = completed_at

            supervisor_run.execution_status = "COMPLETED"

        supervisor_run.output_data = make_json_safe(results)

        supervisor_run.latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        supervisor_run.completed_at = completed_at

        db.commit()

        return {
            "success": not results["errors"],
            "message": (
                "Supervisor completed with resolution plans awaiting approval."
                if results["resolution_plans"]
                else (
                    "Supervisor execution completed with errors."
                    if results["errors"]
                    else "Supervisor execution completed successfully."
                )
            ),
            "workflow_id": workflow_id,
            "workflow_status": workflow.status,
            "current_node": workflow.current_node,
            "result": results
        }

    except Exception as error:

        db.rollback()

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        supervisor_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.run_id == supervisor_run_id
            )
            .first()
        )

        if workflow:

            workflow.status = "FAILED"
            workflow.current_node = "SUPERVISOR_FAILED"
            workflow.error_message = str(error)
            workflow.completed_at = datetime.now()

        if supervisor_run:

            fail_agent_run(
                db,
                supervisor_run,
                error
            )

        db.commit()

        raise


# ======================================================
# CONTINUE AFTER HUMAN APPROVAL
# ======================================================

def continue_supervisor(
    db: Session,
    action_id: int
):

    # --------------------------------------------------
    # 1. FIND ACTION
    # --------------------------------------------------

    action = (
        db.query(Action)
        .filter(
            Action.action_id == action_id
        )
        .first()
    )

    if action is None:

        raise ValueError(
            f"Action {action_id} was not found."
        )

    if action.approval_status != "APPROVED":

        raise ValueError(
            "This action must be approved before execution."
        )

    if action.execution_status == "SUCCEEDED":

        raise ValueError(
            "This action has already been executed successfully."
        )

    if action.execution_status in ["EXECUTING", "FAILED", "SKIPPED"]:

        raise ValueError(
            f"This action cannot be continued from its current "
            f"execution status: {action.execution_status}."
        )

    payload = dict(action.action_payload or {})

    supervisor_workflow_id = payload.get(
        "supervisor_workflow_id"
    )

    supervisor_run_id = payload.get(
        "supervisor_run_id"
    )

    exception_id = payload.get("exception_id")

    if not exception_id:

        raise ValueError(
            "The approved action does not contain an exception ID."
        )

    # --------------------------------------------------
    # 2. EXECUTE ACTION
    # --------------------------------------------------

    execution_result = execute_action(
        db=db,
        action_id=action_id
    )

    if not execution_result.get("success"):

        return {
            "success": False,
            "message": "Action execution failed.",
            "execution": execution_result
        }

    # --------------------------------------------------
    # 3. VERIFY RESOLUTION
    # --------------------------------------------------

    verification_result = verify_exception_resolution(
        db=db,
        exception_id=exception_id
    )

    verification_status = verification_result.get(
        "verification_status",
        "INCONCLUSIVE"
    )

    resolution_verified = (
        verification_status == "VERIFIED"
    )

    # --------------------------------------------------
    # 4. UPDATE SUPERVISOR WORKFLOW
    # --------------------------------------------------

    workflow = None
    supervisor_run = None

    if supervisor_workflow_id:

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == supervisor_workflow_id
            )
            .first()
        )

    if supervisor_run_id:

        supervisor_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.run_id == supervisor_run_id
            )
            .first()
        )

    if workflow:

        workflow.current_node = (
            "RESOLUTION_VERIFIED"
            if resolution_verified
            else "RESOLUTION_NOT_VERIFIED"
        )

        # The workflow has finished its execution cycle.
        # Verification outcome is recorded separately.
        workflow.status = "COMPLETED"
        workflow.completed_at = datetime.now()

    if supervisor_run:

        previous_output = dict(
            supervisor_run.output_data or {}
        )

        previous_output["action_execution"] = execution_result
        previous_output["verification"] = verification_result
        previous_output["resolution_verified"] = resolution_verified

        supervisor_run.output_data = make_json_safe(previous_output)

        supervisor_run.execution_status = "COMPLETED"
        supervisor_run.completed_at = datetime.now()

    db.commit()

    return {
        "success": resolution_verified,
        "message": (
            "The exception resolution was verified successfully."
            if resolution_verified
            else (
                "The action executed, but the exception resolution "
                "could not be verified."
            )
        ),
        "action_execution": execution_result,
        "verification": verification_result,
        "verification_status": verification_status,
        "resolution_verified": resolution_verified,
        "supervisor_workflow_status": (
            workflow.status if workflow else None
        )
    }
