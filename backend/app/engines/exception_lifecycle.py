from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Exception as ShipmentException,
    ExceptionStatusHistory
)


ACTIVE_EXCEPTION_STATUSES = [
    "OPEN",
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE",
    "PENDING_3RD_PARTY"
]

PROTECTED_EXCEPTION_STATUSES = [
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE",
    "PENDING_3RD_PARTY"
]

ALL_EXCEPTION_STATUSES = ACTIVE_EXCEPTION_STATUSES + ["RESOLVED", "CLOSED"]


def get_active_exception(db: Session, shipment_id: int, exception_type: str):
    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.exception_type == exception_type,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .first()
    )


def get_active_exceptions_for_shipment(db: Session, shipment_id: int):
    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .order_by(ShipmentException.detected_at.desc())
        .all()
    )


def _minutes_between(start, end):
    if start is None or end is None:
        return 0
    return max(0, int((end - start).total_seconds() // 60))


def transition_exception_status(
    db: Session,
    exception_id: int,
    new_status: str,
    operator_id: int = None,
    commit: bool = True,
    resolution_notes: str = None
):
    """
    Change an exception status and append an immutable history row.

    Only PENDING_3RD_PARTY pauses the SLA clock. Existing internal states
    such as AWAITING_APPROVAL and AWAITING_RESPONSE continue counting.
    """
    if new_status not in ALL_EXCEPTION_STATUSES:
        raise ValueError(f"Unsupported exception status: {new_status}")

    exception = (
        db.query(ShipmentException)
        .filter(ShipmentException.exception_id == exception_id)
        .with_for_update()
        .first()
    )
    if exception is None:
        raise ValueError(f"Exception ID {exception_id} not found.")

    old_status = exception.status
    if old_status == new_status:
        return {
            "success": True,
            "message": "Exception already has the requested status.",
            "exception_id": exception_id,
            "status": old_status
        }

    if old_status in ("RESOLVED", "CLOSED"):
        raise ValueError("A resolved or closed exception cannot be reopened.")

    changed_at = datetime.now()

    # Leaving an external-wait state closes the most recent pause interval.
    if old_status == "PENDING_3RD_PARTY":
        pause_started = (
            db.query(ExceptionStatusHistory)
            .filter(
                ExceptionStatusHistory.exception_id == exception_id,
                ExceptionStatusHistory.new_status == "PENDING_3RD_PARTY"
            )
            .order_by(ExceptionStatusHistory.changed_at.desc(),
                      ExceptionStatusHistory.log_id.desc())
            .first()
        )
        if pause_started:
            exception.total_paused_minutes = (
                (exception.total_paused_minutes or 0)
                + _minutes_between(pause_started.changed_at, changed_at)
            )

    if new_status == "INVESTIGATING" and exception.acknowledged_at is None:
        exception.acknowledged_at = changed_at

    exception.status = new_status

    if new_status == "RESOLVED":
        exception.resolved_at = changed_at
        if resolution_notes is not None:
            exception.resolution_notes = resolution_notes.strip()

    db.add(ExceptionStatusHistory(
        exception_id=exception_id,
        old_status=old_status,
        new_status=new_status,
        changed_at=changed_at,
        operator_id=operator_id
    ))

    if commit:
        db.commit()
        db.refresh(exception)
    else:
        db.flush()

    return {
        "success": True,
        "exception_id": exception.exception_id,
        "old_status": old_status,
        "status": exception.status,
        "changed_at": changed_at,
        "acknowledged_at": exception.acknowledged_at,
        "resolved_at": exception.resolved_at,
        "total_paused_minutes": exception.total_paused_minutes
    }


def create_or_update_exception(
    db: Session,
    shipment_id: int,
    exception_type: str,
    description: str,
    severity: str = "MEDIUM",
    document_id: int = None,
    event_id: int = None,
    detected_by: str = "MONITORING_AGENT",
    commit: bool = True,
    operator_id: int = None
):
    try:
        existing = get_active_exception(db, shipment_id, exception_type)

        if existing:
            if existing.status in PROTECTED_EXCEPTION_STATUSES:
                return {
                    "success": True,
                    "operation": "SKIPPED",
                    "exception_id": existing.exception_id,
                    "exception": existing,
                    "message": "Existing exception is being handled by another workflow."
                }

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

        # Record the initial state as the first ledger entry.
        db.add(ExceptionStatusHistory(
            exception_id=new_exception.exception_id,
            old_status=None,
            new_status="OPEN",
            changed_at=new_exception.detected_at or datetime.now(),
            operator_id=operator_id
        ))

        if commit:
            db.commit()
            db.refresh(new_exception)
        else:
            db.flush()

        return {
            "success": True,
            "operation": "CREATED",
            "exception_id": new_exception.exception_id,
            "exception": new_exception
        }

    except Exception:
        db.rollback()
        raise


def resolve_exception(
    db: Session,
    exception_id: int,
    resolution_notes: str,
    verified: bool = False,
    commit: bool = True,
    operator_id: int = None
):
    if not verified:
        raise ValueError("Exception cannot be resolved without verification.")
    if not resolution_notes or not resolution_notes.strip():
        raise ValueError("Resolution notes are required.")

    try:
        exception = (
            db.query(ShipmentException)
            .filter(ShipmentException.exception_id == exception_id)
            .with_for_update()
            .first()
        )
        if exception is None:
            raise ValueError(f"Exception ID {exception_id} not found.")

        if exception.status in ("RESOLVED", "CLOSED"):
            return {
                "success": True,
                "message": "Exception is already resolved.",
                "exception_id": exception_id,
                "status": exception.status
            }

        exception.resolution_notes = resolution_notes.strip()
        result = transition_exception_status(
            db=db,
            exception_id=exception_id,
            new_status="RESOLVED",
            operator_id=operator_id,
            commit=commit,
            resolution_notes=resolution_notes.strip()
        )
        result["message"] = "Exception resolved successfully."
        return result

    except Exception:
        db.rollback()
        raise
