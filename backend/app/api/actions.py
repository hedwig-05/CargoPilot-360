
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database.connection import get_db
from app.models import Action, ActionExecution, ResolutionPlan
from app.models.user import User

from app.api.helpers import (
    serialize_records,
    get_all_records
)

from app.auth.dependencies import (
    require_roles
)

from app.engines.human_approval import (
    approve_action,
    reject_action
)

from app.engines.action_executor import (
    execute_action
)


router = APIRouter(
    prefix="/api",
    tags=["Actions"]
)


# ==================================================
# REQUEST SCHEMA
# ==================================================

class RejectionRequest(BaseModel):
    rejection_reason: str = Field(
        min_length=1,
        max_length=1000
    )


# ==================================================
# GET ALL ACTIONS
# ==================================================

@router.get("/actions")
def get_all_actions(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, Action)

    return serialize_records(records, Action)


# ==================================================
# GET ACTIONS AWAITING HUMAN APPROVAL
# ==================================================

@router.get("/actions/pending-approval")
def get_pending_approval_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    """
    Return the action queue that authorized managers can review.

    This endpoint is read-only. It never approves or executes actions.
    """

    records = (
        db.query(Action, ResolutionPlan)
        .join(
            ResolutionPlan,
            Action.plan_id == ResolutionPlan.plan_id
        )
        .filter(
            Action.requires_approval.is_(True),
            Action.approval_status == "PENDING",
            Action.execution_status == "NOT_STARTED",
            ResolutionPlan.status == "PENDING_APPROVAL"
        )
        .order_by(
            Action.created_at.asc(),
            Action.action_id.asc()
        )
        .all()
    )

    return [
        {
            "action_id": action.action_id,
            "plan_id": plan.plan_id,
            "workflow_id": action.workflow_id,
            "action_type": action.action_type,
            "action_description": action.action_description,
            "action_payload": action.action_payload,
            "approval_status": action.approval_status,
            "execution_status": action.execution_status,
            "created_at": action.created_at,
            "plan_priority": plan.priority,
            "plan_status": plan.status,
            "proposed_solution": plan.proposed_solution,
            "reasoning": plan.reasoning
        }
        for action, plan in records
    ]


# ==================================================
# GET ALL ACTION EXECUTIONS
# ==================================================

@router.get("/action-executions")
def get_all_action_executions(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, ActionExecution)

    return serialize_records(records, ActionExecution)


# ==================================================
# GET EXECUTIONS FOR A SPECIFIC ACTION
# ==================================================

@router.get("/actions/{action_id}/executions")
def get_action_executions(
    action_id: int,
    db: Session = Depends(get_db)
):
    records = db.query(ActionExecution).filter(
        ActionExecution.action_id == action_id
    ).all()

    return serialize_records(records, ActionExecution)


# ==================================================
# APPROVE ACTION
# ==================================================

@router.post("/actions/{action_id}/approve")
def approve_action_endpoint(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    try:
        return approve_action(
            db=db,
            action_id=action_id,
            approver=current_user
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error)
        )


# ==================================================
# REJECT ACTION
# ==================================================

@router.post("/actions/{action_id}/reject")
def reject_action_endpoint(
    action_id: int,
    request: RejectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    try:
        return reject_action(
            db=db,
            action_id=action_id,
            approver=current_user,
            rejection_reason=request.rejection_reason
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error)
        )


# ==================================================
# EXECUTE APPROVED ACTION
# ==================================================

@router.post("/actions/{action_id}/execute")
def execute_action_endpoint(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    try:
        return execute_action(
            db=db,
            action_id=action_id
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error)
        )
