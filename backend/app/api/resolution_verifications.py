
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import require_roles

from app.models import (
    ResolutionVerification
)

from app.engines.resolution_verification import (
    verify_exception_resolution
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/resolution-verifications",
    tags=["Resolution Verifications"]
)


# ==========================================================
# VERIFY EXCEPTION RESOLUTION
# ==========================================================

@router.post("/exceptions/{exception_id}/verify")
def verify_exception(
    exception_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles("ADMIN", "MANAGER")
    )
):

    try:

        result = verify_exception_resolution(
            db=db,
            exception_id=exception_id,
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
            "Resolution verification failed for exception %s",
            exception_id
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Resolution verification failed. "
                "Check backend logs for details."
            )
        )


# ==========================================================
# GET ALL RESOLUTION VERIFICATIONS
# ==========================================================

@router.get("/")
def get_all_verifications(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles("ADMIN", "MANAGER")
    )
):

    records = (
        db.query(ResolutionVerification)
        .order_by(
            ResolutionVerification.verified_at.desc(),
            ResolutionVerification.verification_id.desc()
        )
        .all()
    )

    return records


# ==========================================================
# GET VERIFICATION HISTORY FOR AN EXCEPTION
# ==========================================================

@router.get("/exceptions/{exception_id}")
def get_exception_verifications(
    exception_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles("ADMIN", "MANAGER")
    )
):

    records = (
        db.query(ResolutionVerification)
        .filter(
            ResolutionVerification.exception_id == exception_id
        )
        .order_by(
            ResolutionVerification.verified_at.desc(),
            ResolutionVerification.verification_id.desc()
        )
        .all()
    )

    return records
