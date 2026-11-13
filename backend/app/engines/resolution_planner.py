
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Exception as ShipmentException,
    AgentWorkflow,
    AgentRun,
    Investigation,
    RiskAssessment,
    ResolutionPlan,
    Action
)


# ==================================================
# RESOLUTION RULES
# ==================================================

RESOLUTION_RULES = {

    "DOCUMENT_MISMATCH": {
        "action_type": "REQUEST_DOCUMENT_CORRECTION",
        "description": (
            "Request corrected shipping documents "
            "from the responsible stakeholder."
        )
    },

    "MISSING_DOCUMENT": {
        "action_type": "REQUEST_MISSING_DOCUMENT",
        "description": (
            "Request the missing mandatory shipping document."
        )
    },

    "SHIPMENT_DELAY": {
        "action_type": "NOTIFY_OPERATIONS_OFFICER",
        "description": (
            "Notify the operations officer about the shipment delay."
        )
    },

    "MISSING_MILESTONE": {
        "action_type": "NOTIFY_OPERATIONS_OFFICER",
        "description": (
            "Notify the operations officer about the missing milestone."
        )
    },

    "CUSTOMS_HOLD": {
        "action_type": "ESCALATE_TO_MANAGER",
        "description": (
            "Escalate the customs hold for managerial review."
        )
    },

    "STAKEHOLDER_RESPONSE_DELAY": {
        "action_type": "SEND_FOLLOW_UP_EMAIL",
        "description": (
            "Send a follow-up request to the responsible stakeholder."
        )
    },

    "CONTAINER_NOT_DISCHARGED": {
        "action_type": "ESCALATE_TO_MANAGER",
        "description": (
            "Escalate the container discharge issue to management."
        )
    }
}


# ==================================================
# DETERMINE PLAN PRIORITY
# ==================================================

def determine_plan_priority(exception, risk):

    severity = exception.severity

    if risk:

        risk_level = risk.risk_level

        if risk_level == "HIGH" or severity == "CRITICAL":
            return "URGENT"

        if risk_level == "MEDIUM" or severity == "HIGH":
            return "HIGH"

    if severity == "CRITICAL":
        return "URGENT"

    if severity == "HIGH":
        return "HIGH"

    if severity == "MEDIUM":
        return "MEDIUM"

    return "LOW"


# ==================================================
# GENERATE RESOLUTION REASONING
# ==================================================

def generate_resolution_reasoning(exception, investigation, risk):

    reasoning_parts = [
        f"Exception type: {exception.exception_type}",
        f"Severity: {exception.severity}",
        f"Description: {exception.description}"
    ]

    if investigation:

        reasoning_parts.append(
            f"Investigation summary: {investigation.summary}"
        )

        if investigation.possible_cause:

            reasoning_parts.append(
                f"Possible cause: {investigation.possible_cause}"
            )

        if investigation.recommended_next:

            reasoning_parts.append(
                f"Investigation recommendation: "
                f"{investigation.recommended_next}"
            )

    if risk:

        reasoning_parts.append(
            f"Risk score: {risk.risk_score}"
        )

        reasoning_parts.append(
            f"Risk level: {risk.risk_level}"
        )

        if risk.explanation:

            reasoning_parts.append(
                f"Risk explanation: {risk.explanation}"
            )

    return "\n".join(reasoning_parts)


# ==================================================
# CREATE RESOLUTION PLAN
# ==================================================

def create_resolution_plan(
    db: Session,
    exception_id: int,
    triggered_by: int = None
):

    started_at = datetime.now()

    try:

        # ------------------------------------------
        # 1. GET EXCEPTION
        # ------------------------------------------

        exception = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.exception_id == exception_id
            )
            .with_for_update()
            .first()
        )

        if not exception:
            raise ValueError(
                f"Exception {exception_id} not found."
            )

        if exception.status in ["RESOLVED", "CLOSED"]:
            raise ValueError(
                "Cannot create a resolution plan "
                "for a resolved or closed exception."
            )

        # ------------------------------------------
        # 2. PREVENT DUPLICATE ACTIVE PLANS
        # ------------------------------------------

        existing_plan = (
            db.query(ResolutionPlan)
            .filter(
                ResolutionPlan.exception_id == exception_id,
                ResolutionPlan.status.in_([
                    "DRAFT",
                    "PENDING_APPROVAL",
                    "APPROVED",
                    "EXECUTING"
                ])
            )
            .first()
        )

        if existing_plan:
            raise ValueError(
                f"An active resolution plan already exists: "
                f"{existing_plan.plan_id}"
            )

        # ------------------------------------------
        # 3. GET LATEST COMPLETED INVESTIGATION
        # ------------------------------------------

        investigation = (
            db.query(Investigation)
            .filter(
                Investigation.exception_id == exception_id,
                Investigation.status == "COMPLETED"
            )
            .order_by(
                Investigation.created_at.desc(),
                Investigation.investigation_id.desc()
            )
            .first()
        )

        if not investigation:
            raise ValueError(
                "A completed investigation is required "
                "before creating a resolution plan."
            )

        # ------------------------------------------
        # 4. GET MATCHING RISK ASSESSMENT
        # ------------------------------------------

        risk = (
            db.query(RiskAssessment)
            .filter(
                RiskAssessment.exception_id == exception_id,
                RiskAssessment.workflow_id == investigation.workflow_id,
                RiskAssessment.shipment_id == exception.shipment_id
            )
            .order_by(
                RiskAssessment.assessed_at.desc(),
                RiskAssessment.risk_id.desc()
            )
            .first()
        )

        if not risk:
            raise ValueError(
                "No matching risk assessment was found "
                "for this exception and workflow."
            )

        # ------------------------------------------
        # 5. GET WORKFLOW
        # ------------------------------------------

        # exception_id is intentionally NOT used here.
        # One workflow can handle multiple exceptions.

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == risk.workflow_id,
                AgentWorkflow.shipment_id == exception.shipment_id
            )
            .first()
        )

        if not workflow:
            raise ValueError(
                "The workflow associated with the risk assessment "
                "could not be found."
            )

        # ------------------------------------------
        # 6. GET RESOLUTION RULE
        # ------------------------------------------

        rule = RESOLUTION_RULES.get(
            exception.exception_type
        )

        if not rule:
            raise ValueError(
                f"No resolution rule defined for "
                f"{exception.exception_type}"
            )

        # ------------------------------------------
        # 7. DETERMINE PRIORITY
        # ------------------------------------------

        priority = determine_plan_priority(
            exception,
            risk
        )

        # ------------------------------------------
        # 8. GET NEXT WORKFLOW STEP
        # ------------------------------------------

        current_max_step = (
            db.query(func.max(AgentRun.step_no))
            .filter(
                AgentRun.workflow_id == workflow.workflow_id
            )
            .scalar()
        ) or 0

        # ------------------------------------------
        # 9. CREATE DECISION AGENT RUN
        # ------------------------------------------

        decision_run = AgentRun(
            run_public_id=(
                f"RUN-{uuid.uuid4().hex[:12].upper()}"
            ),

            workflow_id=workflow.workflow_id,

            parent_run_id=risk.run_id,

            step_no=current_max_step + 1,

            agent_type="DECISION",

            node_name="resolution_planner",

            input_data={
                "exception_id": exception_id,
                "shipment_id": exception.shipment_id,
                "exception_type": exception.exception_type,
                "investigation_id": investigation.investigation_id,
                "risk_id": risk.risk_id,
                "risk_score": float(risk.risk_score),
                "risk_level": risk.risk_level
            },

            execution_status="PROCESSING"
        )

        db.add(decision_run)
        db.flush()

        # ------------------------------------------
        # 10. GENERATE REASONING
        # ------------------------------------------

        reasoning = generate_resolution_reasoning(
            exception,
            investigation,
            risk
        )

        # ------------------------------------------
        # 11. DETERMINE PLAN VERSION
        # ------------------------------------------

        version_no = (
            db.query(ResolutionPlan)
            .filter(
                ResolutionPlan.exception_id == exception_id
            )
            .count() + 1
        )

        # ------------------------------------------
        # 12. CREATE RESOLUTION PLAN
        # ------------------------------------------

        plan = ResolutionPlan(
            exception_id=exception_id,
            workflow_id=workflow.workflow_id,
            run_id=decision_run.run_id,
            investigation_id=investigation.investigation_id,
            risk_id=risk.risk_id,
            version_no=version_no,
            proposed_solution=rule["description"],
            reasoning=reasoning,
            priority=priority,
            status="PENDING_APPROVAL"
        )

        db.add(plan)
        db.flush()

        # ------------------------------------------
        # 13. CREATE RECOMMENDED ACTION
        # ------------------------------------------

        action = Action(
            plan_id=plan.plan_id,
            workflow_id=workflow.workflow_id,
            created_by_run_id=decision_run.run_id,
            action_type=rule["action_type"],
            action_description=rule["description"],

            action_payload={
                "exception_id": exception_id,
                "shipment_id": exception.shipment_id,
                "exception_type": exception.exception_type,
                "plan_id": plan.plan_id
            },

            requires_approval=True,
            approval_status="PENDING",
            execution_status="NOT_STARTED",

            idempotency_key=(
                f"PLAN-{plan.plan_id}-ACTION-"
                f"{uuid.uuid4().hex.upper()}"
            )
        )

        db.add(action)
        db.flush()

        # ------------------------------------------
        # 14. UPDATE DECISION RUN
        # ------------------------------------------

        completed_at = datetime.now()

        decision_run.output_data = {
            "plan_id": plan.plan_id,
            "action_id": action.action_id,
            "priority": priority,
            "plan_status": "PENDING_APPROVAL",
            "action_type": rule["action_type"],
            "action_status": "PENDING",
            "investigation_id": investigation.investigation_id,
            "risk_id": risk.risk_id,
            "workflow_id": workflow.workflow_id
        }

        decision_run.execution_status = "COMPLETED"

        decision_run.latency_ms = int(
            (completed_at - started_at).total_seconds() * 1000
        )

        decision_run.completed_at = completed_at

        # ------------------------------------------
        # 15. UPDATE EXCEPTION AND WORKFLOW
        # ------------------------------------------

        exception.status = "AWAITING_APPROVAL"

        workflow.status = "WAITING_FOR_APPROVAL"

        workflow.current_node = "WAITING_FOR_APPROVAL"

        # ------------------------------------------
        # 16. COMMIT
        # ------------------------------------------

        db.commit()

        return {
            "message": "Resolution plan created successfully.",
            "exception_id": exception_id,
            "workflow_id": workflow.workflow_id,
            "run_id": decision_run.run_id,
            "investigation_id": investigation.investigation_id,
            "risk_id": risk.risk_id,
            "plan_id": plan.plan_id,
            "action_id": action.action_id,
            "version_no": version_no,
            "priority": priority,
            "plan_status": plan.status,
            "action_type": action.action_type,
            "approval_status": action.approval_status,
            "execution_status": action.execution_status,
            "reasoning": reasoning
        }

    except Exception:

        db.rollback()
        raise
