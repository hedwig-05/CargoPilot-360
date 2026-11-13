
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Investigation
from app.api.helpers import serialize_records, get_all_records


router = APIRouter(
    prefix="/api",
    tags=["Investigations"]
)


# GET ALL INVESTIGATIONS

@router.get("/investigations")
def get_all_investigations(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, Investigation)

    return serialize_records(records, Investigation)


# GET INVESTIGATIONS FOR A SHIPMENT

@router.get("/shipments/{shipment_id}/investigations")
def get_shipment_investigations(
    shipment_id: int,
    db: Session = Depends(get_db)
):
    records = db.query(Investigation).filter(
        Investigation.shipment_id == shipment_id
    ).all()

    return serialize_records(records, Investigation)
