
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import ShipmentEvent


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
