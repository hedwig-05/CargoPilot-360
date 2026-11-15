
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import ShipmentEvent, AuditLog
from app.models.user import User
from app.auth.dependencies import require_roles
from app.engines.milestone_reconciliation import assess_milestone_reconciliation


router = APIRouter(
    prefix="/api/shipments",
    tags=["Shipment Events"]
)


# ==========================================
# GET SHIPMENT TRACKING EVENTS
# ==========================================

@router.get("/{shipment_id}/events")
def get_shipment_events(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    events = db.query(ShipmentEvent).filter(
        ShipmentEvent.shipment_id == shipment_id
    ).order_by(
        ShipmentEvent.expected_time.asc()
    ).all()

    return [
        {
            "event_id": event.event_id,
            "shipment_id": event.shipment_id,
            "event_type": event.event_type,
            "event_description": event.event_description,
            "expected_time": event.expected_time,
            "actual_time": event.actual_time,
            "event_status": event.event_status,
            "source": event.source,
            "created_at": event.created_at
        }
        for event in events
    ]



# ==========================================
# MILESTONE RECONCILIATION PREVIEW
# ==========================================

@router.get("/{shipment_id}/events/{event_id}/reconciliation")
def get_event_reconciliation(
    shipment_id: int,
    event_id: int,
    db: Session = Depends(get_db)
):
    event = db.query(ShipmentEvent).filter(
        ShipmentEvent.event_id == event_id,
        ShipmentEvent.shipment_id == shipment_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment event not found."
        )

    return assess_milestone_reconciliation(
        db=db,
        event=event
    )


# ==========================================
# HUMAN CONFIRMATION REQUEST
# ==========================================

class MilestoneConfirmationRequest(BaseModel):
    actual_time: datetime
    evidence_note: str = Field(min_length=10, max_length=1000)


# ==========================================
# CONFIRM OPERATIONAL MILESTONE
# ==========================================

@router.post("/events/{event_id}/confirm")
def confirm_shipment_event(
    event_id: int,
    request: MilestoneConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    event = db.query(ShipmentEvent).filter(
        ShipmentEvent.event_id == event_id
    ).with_for_update().first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment event not found."
        )

    if event.event_type != "DOCUMENTATION_COMPLETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This confirmation endpoint currently supports DOCUMENTATION_COMPLETE events only."
        )

    if event.event_status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This milestone is already completed."
        )

    if request.actual_time > datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Actual milestone time cannot be in the future."
        )

    assessment = assess_milestone_reconciliation(
        db=db,
        event=event
    )

    if not assessment["ready_for_confirmation"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Milestone cannot be confirmed because document evidence is not sufficient.",
                "assessment": assessment
            }
        )

    previous_status = event.event_status
    previous_actual_time = event.actual_time

    event.actual_time = request.actual_time
    event.event_status = "COMPLETED"
    event.source = "USER_CONFIRMED"

    db.add(AuditLog(
        actor_type="USER",
        actor_user_id=current_user.user_id,
        actor_name=current_user.name,
        action="SHIPMENT_MILESTONE_CONFIRMED",
        entity_type="SHIPMENT_EVENT",
        entity_id=event.event_id,
        shipment_id=event.shipment_id,
        details={
            "event_type": event.event_type,
            "previous_status": previous_status,
            "new_status": "COMPLETED",
            "previous_actual_time": (
                previous_actual_time.isoformat()
                if previous_actual_time else None
            ),
            "actual_time": request.actual_time.isoformat(),
            "evidence_note": request.evidence_note
        }
    ))

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Milestone confirmed and audit record created.",
        "event_id": event.event_id,
        "shipment_id": event.shipment_id,
        "event_type": event.event_type,
        "previous_status": previous_status,
        "event_status": event.event_status,
        "actual_time": event.actual_time,
        "source": event.source
    }
