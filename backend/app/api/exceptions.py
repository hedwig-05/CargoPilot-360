from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.models import Exception, ExceptionStatusHistory, User
from app.engines.exception_lifecycle import (
    transition_exception_status,
    ALL_EXCEPTION_STATUSES
)


router = APIRouter(prefix="/api", tags=["Exceptions"])

# Response-time targets, in hours, aligned with the eight-factor model.
RESPONSE_SLA_HOURS = {
    "DAMAGE_SHORTAGE": 2,
    "DOCUMENT_MISMATCH": 2,
    "CUSTOMS_ISSUE": 4,
    "ROLLED_CARGO": 4,
    "ARRIVAL_DELAY": 24,
    "MISSING_MILESTONE": 24,
    "MISSING_DOCUMENT": 48,
    "STAKEHOLDER_DELAY": 48
}


class ExceptionStatusUpdate(BaseModel):
    status: str
    resolution_notes: str | None = Field(default=None, max_length=4000)


def _risk_factor_for_exception(exception, db):
    if exception.exception_type == "DAMAGE_SHORTAGE":
        return "DAMAGE_SHORTAGE"
    if exception.exception_type == "ROLLED_CARGO":
        return "ROLLED_CARGO"
    if exception.exception_type == "DOCUMENT_MISMATCH":
        return "DOCUMENT_MISMATCH"
    if exception.exception_type == "MISSING_DOCUMENT":
        return "MISSING_DOCUMENT"
    if exception.exception_type == "CUSTOMS_HOLD":
        return "CUSTOMS_ISSUE"
    if exception.exception_type == "STAKEHOLDER_RESPONSE_DELAY":
        return "STAKEHOLDER_DELAY"
    if exception.exception_type in ("MISSING_MILESTONE", "CONTAINER_NOT_DISCHARGED"):
        return "MISSING_MILESTONE"
    if exception.exception_type == "SHIPMENT_DELAY":
        from app.models import ShipmentEvent
        event = None
        if exception.event_id:
            event = db.query(ShipmentEvent).filter(
                ShipmentEvent.event_id == exception.event_id
            ).first()
        customs_delay = event and event.event_type == "CUSTOMS_CLEARED"
        customs_delay = customs_delay or "CUSTOMS_CLEARED" in (exception.description or "")
        return "CUSTOMS_ISSUE" if customs_delay else "ARRIVAL_DELAY"
    return None


def _sla_metrics(exception, db):
    now = datetime.now()
    history = (
        db.query(ExceptionStatusHistory)
        .filter(ExceptionStatusHistory.exception_id == exception.exception_id)
        .order_by(ExceptionStatusHistory.changed_at.asc(), ExceptionStatusHistory.log_id.asc())
        .all()
    )

    pause_started = None
    paused_seconds = 0
    pause_intervals = []
    for entry in history:
        if entry.new_status == "PENDING_3RD_PARTY":
            pause_started = entry.changed_at
        elif pause_started is not None:
            end = entry.changed_at
            if end > pause_started:
                paused_seconds += (end - pause_started).total_seconds()
                pause_intervals.append((pause_started, end))
            pause_started = None

    currently_paused = exception.status == "PENDING_3RD_PARTY"
    if currently_paused and pause_started is not None and now > pause_started:
        paused_seconds += (now - pause_started).total_seconds()
        pause_intervals.append((pause_started, now))

    end_time = exception.resolved_at or now
    gross_seconds = max(0, (end_time - exception.detected_at).total_seconds())
    net_seconds = max(0, gross_seconds - paused_seconds)

    tta_minutes = None
    tta_net_minutes = None
    if exception.acknowledged_at is not None:
        tta_seconds = max(0, (exception.acknowledged_at - exception.detected_at).total_seconds())
        tta_paused_seconds = sum(
            max(0, (min(b, exception.acknowledged_at) - max(a, exception.detected_at)).total_seconds())
            for a, b in pause_intervals
            if min(b, exception.acknowledged_at) > max(a, exception.detected_at)
        )
        tta_minutes = round(tta_seconds / 60, 2)
        tta_net_minutes = round(max(0, tta_seconds - tta_paused_seconds) / 60, 2)

    factor = _risk_factor_for_exception(exception, db)
    target_hours = RESPONSE_SLA_HOURS.get(factor)
    if tta_net_minutes is not None:
        response_elapsed_minutes = tta_net_minutes
    elif exception.status == "OPEN" or currently_paused:
        elapsed_seconds = max(0, (now - exception.detected_at).total_seconds())
        response_elapsed_minutes = round(
            max(0, elapsed_seconds - min(paused_seconds, elapsed_seconds)) / 60,
            2
        )
    else:
        # This exception was already beyond OPEN before acknowledgement
        # timestamps were introduced. Do not invent a historical TTA.
        response_elapsed_minutes = None

    if target_hours is None:
        sla_status = "UNMAPPED"
    elif exception.acknowledged_at is not None:
        sla_status = "MET" if response_elapsed_minutes <= target_hours * 60 else "BREACHED"
    elif currently_paused:
        sla_status = "PAUSED"
    elif exception.status != "OPEN":
        sla_status = "ACKNOWLEDGEMENT_NOT_RECORDED"
    else:
        sla_status = "BREACHED" if response_elapsed_minutes > target_hours * 60 else "WITHIN_SLA"

    return {
        "risk_factor": factor,
        "response_sla_hours": target_hours,
        "response_elapsed_minutes": response_elapsed_minutes,
        "sla_status": sla_status,
        "tta_minutes": tta_minutes,
        "tta_net_minutes": tta_net_minutes,
        "gross_ttr_minutes": round(gross_seconds / 60, 2),
        "net_ttr_minutes": round(net_seconds / 60, 2),
        "total_paused_minutes": round(paused_seconds / 60, 2),
        "is_sla_clock_paused": currently_paused
    }


def _serialize_exception(exception, db):
    return {
        "exception_id": exception.exception_id,
        "shipment_id": exception.shipment_id,
        "exception_type": exception.exception_type,
        "description": exception.description,
        "severity": exception.severity,
        "status": exception.status,
        "detected_at": exception.detected_at,
        "acknowledged_at": exception.acknowledged_at,
        "resolved_at": exception.resolved_at,
        "total_paused_minutes": exception.total_paused_minutes,
        "sla": _sla_metrics(exception, db)
    }


@router.get("/exceptions")
def get_all_exceptions(db: Session = Depends(get_db)):
    exceptions = db.query(Exception).order_by(Exception.exception_id.desc()).all()
    return [_serialize_exception(item, db) for item in exceptions]


@router.get("/shipments/{shipment_id}/exceptions")
def get_shipment_exceptions(shipment_id: int, db: Session = Depends(get_db)):
    exceptions = (
        db.query(Exception)
        .filter(Exception.shipment_id == shipment_id)
        .order_by(Exception.exception_id.desc())
        .all()
    )
    return [_serialize_exception(item, db) for item in exceptions]


@router.get("/exceptions/{exception_id}/history")
def get_exception_status_history(exception_id: int, db: Session = Depends(get_db)):
    exception = db.query(Exception).filter(Exception.exception_id == exception_id).first()
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found.")

    rows = (
        db.query(ExceptionStatusHistory)
        .filter(ExceptionStatusHistory.exception_id == exception_id)
        .order_by(ExceptionStatusHistory.changed_at.asc(), ExceptionStatusHistory.log_id.asc())
        .all()
    )
    return [
        {
            "log_id": row.log_id,
            "exception_id": row.exception_id,
            "old_status": row.old_status,
            "new_status": row.new_status,
            "changed_at": row.changed_at,
            "operator_id": row.operator_id
        }
        for row in rows
    ]


@router.post("/exceptions/{exception_id}/status")
def update_exception_status(
    exception_id: int,
    data: ExceptionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.status not in ALL_EXCEPTION_STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported exception status.")

    if data.status == "RESOLVED":
        raise HTTPException(
            status_code=400,
            detail="Use the resolution verification workflow to resolve an exception."
        )

    try:
        result = transition_exception_status(
            db=db,
            exception_id=exception_id,
            new_status=data.status,
            operator_id=current_user.user_id,
            commit=True
        )
        return result
    except ValueError as error:
        db.rollback()
        message = str(error)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message)
