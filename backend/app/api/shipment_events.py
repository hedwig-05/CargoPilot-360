
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import ShipmentEvent, AuditLog, Shipment
from app.models.user import User
from app.auth.dependencies import get_current_user, require_roles
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

@router.post("/{shipment_id}/events/{event_id}/confirm")
def confirm_shipment_event(
    shipment_id: int,
    event_id: int,
    request: MilestoneConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANAGER")
    )
):
    # Acquire the shipment lock first. Document uploads use the same
    # parent-row lock while selecting document versions and validating them.
    # This serializes confirmation against an in-progress upload/validation
    # transaction and avoids assessing a partially updated document set.
    shipment = db.query(Shipment).filter(
        Shipment.shipment_id == shipment_id
    ).with_for_update().first()

    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found."
        )

    event = db.query(ShipmentEvent).filter(
        ShipmentEvent.event_id == event_id,
        ShipmentEvent.shipment_id == shipment_id
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

    # Store naive UTC consistently because shipment_events.actual_time is a
    # MySQL DATETIME column. Treat offset-free API values as UTC as well.
    actual_time_utc = request.actual_time
    if actual_time_utc.tzinfo is not None:
        actual_time_utc = actual_time_utc.astimezone(timezone.utc).replace(tzinfo=None)

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if actual_time_utc > now_utc:
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

    event.actual_time = actual_time_utc
    event.event_status = "COMPLETED"
    # Keep source unchanged: it participates in simulator event deduplication.

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
            "actual_time": actual_time_utc.isoformat(),
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
