
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Shipment


router = APIRouter(
    prefix="/api/shipments",
    tags=["Shipments"]
)


# ==========================================
# 1. GET ALL SHIPMENTS
# ==========================================

@router.get("/")
def get_all_shipments(db: Session = Depends(get_db)):

    shipments = db.query(Shipment).all()

    return [
        {
            "shipment_id": shipment.shipment_id,
            "shipment_ref": shipment.shipment_ref,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "shipper": shipment.shipper,
            "consignee": shipment.consignee,
            "container_no": shipment.container_no,
            "container_type": shipment.container_type,
            "expected_arrival": shipment.expected_arrival,
            "actual_arrival": shipment.actual_arrival,
            "status": shipment.status,
            "current_risk_score": shipment.current_risk_score,
            "current_risk_level": shipment.current_risk_level
        }
        for shipment in shipments
    ]


# ==========================================
# 2. GET SHIPMENT BY ID
# ==========================================

@router.get("/{shipment_id}")
def get_shipment_by_id(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    shipment = db.query(Shipment).filter(
        Shipment.shipment_id == shipment_id
    ).first()

    if shipment is None:
        return {
            "error": "Shipment not found",
            "shipment_id": shipment_id
        }

    return {
        "shipment_id": shipment.shipment_id,
        "shipment_ref": shipment.shipment_ref,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "shipper": shipment.shipper,
        "consignee": shipment.consignee,
        "container_no": shipment.container_no,
        "container_type": shipment.container_type,
        "expected_arrival": shipment.expected_arrival,
        "actual_arrival": shipment.actual_arrival,
        "status": shipment.status,
        "current_risk_score": shipment.current_risk_score,
        "current_risk_level": shipment.current_risk_level
    }
