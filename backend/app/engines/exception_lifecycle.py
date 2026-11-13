
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Exception as ShipmentException


# ==================================================
# ACTIVE EXCEPTION STATUSES
# ==================================================

ACTIVE_EXCEPTION_STATUSES = [
    "OPEN",
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE"
]


# ==================================================
# EXCEPTION STATUSES PROTECTED FROM MONITORING
# ==================================================

PROTECTED_EXCEPTION_STATUSES = [
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE"
]


# ==================================================
# GET ACTIVE EXCEPTION
# ==================================================

def get_active_exception(
    db: Session,
    shipment_id: int,
    exception_type: str
):
    """
    Retrieve an active exception for a shipment
    and exception type.
    """

    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.exception_type == exception_type,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .first()
    )


# ==================================================
# GET ALL ACTIVE EXCEPTIONS FOR A SHIPMENT
# ==================================================

def get_active_exceptions_for_shipment(
    db: Session,
    shipment_id: int
):
    """
    Retrieve all active exceptions belonging
    to a particular shipment.
    """

    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .order_by(ShipmentException.detected_at.desc())
        .all()
    )


# ==================================================
# CREATE OR UPDATE EXCEPTION
# ==================================================

def create_or_update_exception(
    db: Session,
    shipment_id: int,
    exception_type: str,
    description: str,
    severity: str = "MEDIUM",
    document_id: int = None,
    event_id: int = None,
    detected_by: str = "MONITORING_AGENT",
    commit: bool = True
):
    """
    Create an exception if one does not exist.

    Update an existing OPEN exception.

    Preserve exceptions already being handled
    by investigation, approval or execution workflows.

    Returns CREATED, UPDATED or SKIPPED.
    """

    try:

        existing = get_active_exception(
            db=db,
            shipment_id=shipment_id,
            exception_type=exception_type
        )

        # ------------------------------------------
        # EXISTING EXCEPTION FOUND
        # ------------------------------------------

        if existing:

            # Do not overwrite an exception that
            # another workflow is already handling.

            if existing.status in PROTECTED_EXCEPTION_STATUSES:

                return {
                    "success": True,
                    "operation": "SKIPPED",
                    "exception_id": existing.exception_id,
                    "exception": existing,
                    "message": (
                        "Existing exception is being handled "
                        "by another workflow."
                    )
                }

            # Only OPEN exceptions can be updated.

            existing.description = description
            existing.severity = severity

            if document_id is not None:
                existing.document_id = document_id

            if event_id is not None:
                existing.event_id = event_id

            if commit:
                db.commit()
                db.refresh(existing)
            else:
                db.flush()

            return {
                "success": True,
                "operation": "UPDATED",
                "exception_id": existing.exception_id,
                "exception": existing
            }

        # ------------------------------------------
        # CREATE NEW EXCEPTION
        # ------------------------------------------

        new_exception = ShipmentException(
            shipment_id=shipment_id,
            exception_type=exception_type,
            description=description,
            severity=severity,
            status="OPEN",
            document_id=document_id,
            event_id=event_id,
            detected_by=detected_by
        )

        db.add(new_exception)
        db.flush()

        if commit:
            db.commit()
            db.refresh(new_exception)

        return {
            "success": True,
            "operation": "CREATED",
            "exception_id": new_exception.exception_id,
            "exception": new_exception
        }

    except Exception:
        db.rollback()
        raise


# ==================================================
# RESOLVE EXCEPTION
# ==================================================

def resolve_exception(
    db: Session,
    exception_id: int,
    resolution_notes: str,
    verified: bool = False,
    commit: bool = True
):
    """
    Resolve an exception only after verification.

    The caller must supply verification evidence
    before setting verified=True.

    IMPORTANT:
    verified=True is a caller assertion, not an
    automatic verification of the underlying issue.
    """

    if not verified:
        raise ValueError(
            "Exception cannot be resolved without verification."
        )

    if not resolution_notes or not resolution_notes.strip():
        raise ValueError(
            "Resolution notes are required."
        )

    try:

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
                f"Exception ID {exception_id} not found."
            )

        if exception.status in ["RESOLVED", "CLOSED"]:
            return {
                "success": True,
                "message": "Exception is already resolved.",
                "exception_id": exception_id,
                "status": exception.status
            }

        exception.status = "RESOLVED"
        exception.resolved_at = datetime.now()
        exception.resolution_notes = resolution_notes.strip()

        if commit:
            db.commit()
            db.refresh(exception)
        else:
            db.flush()

        return {
            "success": True,
            "message": "Exception resolved successfully.",
            "exception_id": exception.exception_id,
            "status": exception.status,
            "resolved_at": exception.resolved_at
        }

    except Exception:
        db.rollback()
        raise
