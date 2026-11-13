
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import require_roles

from app.engines.supervisor_agent import (
    run_supervisor,
    continue_supervisor
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/supervisor",
    tags=["Supervisor Agent"]
)


# ==================================================
# START SUPERVISOR WORKFLOW
# ==================================================

@router.post("/shipments/{shipment_id}/run")
def start_supervisor(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles("ADMIN", "MANAGER")
    )
):

    try:

        result = run_supervisor(
            db=db,
            shipment_id=shipment_id,
            triggered_by=current_user.user_id
        )

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception:

        logger.exception(
            "Supervisor execution failed for shipment %s",
            shipment_id
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Supervisor execution failed. "
                "Check backend logs for details."
            )
        )


# ==================================================
# CONTINUE APPROVED SUPERVISOR WORKFLOW
# ==================================================

@router.post("/actions/{action_id}/continue")
def continue_approved_supervisor(
    action_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles("ADMIN", "MANAGER")
    )
):

    try:

        result = continue_supervisor(
            db=db,
            action_id=action_id
        )

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception:

        logger.exception(
            "Supervisor continuation failed for action %s",
            action_id
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Supervisor continuation failed. "
                "Check backend logs for details."
            )
        )
