from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import ResolutionPlan, Exception as ShipmentException
from app.api.helpers import serialize_records, get_all_records


router = APIRouter(
    prefix="/api",
    tags=["Resolution Plans"]
)


# GET ALL RESOLUTION PLANS

@router.get("/resolution-plans")
def get_all_resolution_plans(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, ResolutionPlan)

    return serialize_records(records, ResolutionPlan)


# GET RESOLUTION PLANS FOR A SHIPMENT

@router.get("/shipments/{shipment_id}/resolution-plans")
def get_shipment_resolution_plans(
    shipment_id: int,
    db: Session = Depends(get_db)
):
    records = (
        db.query(ResolutionPlan)
        .join(
            ShipmentException,
            ResolutionPlan.exception_id == ShipmentException.exception_id
        )
        .filter(
            ShipmentException.shipment_id == shipment_id
        )
        .all()
    )

    return serialize_records(records, ResolutionPlan)