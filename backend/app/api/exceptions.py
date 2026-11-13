
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Exception


router = APIRouter(
    prefix="/api",
    tags=["Exceptions"]
)


# ==========================================
# GET ALL SHIPMENT EXCEPTIONS
# ==========================================

@router.get("/exceptions")
def get_all_exceptions(
    db: Session = Depends(get_db)
):

    exceptions = db.query(Exception).order_by(
        Exception.exception_id.desc()
    ).all()

    return [
        {
            "exception_id": exception.exception_id,
            "shipment_id": exception.shipment_id,
            "exception_type": exception.exception_type,
            "description": exception.description,
            "severity": exception.severity,
            "status": exception.status,
            "detected_at": exception.detected_at,
            "resolved_at": exception.resolved_at
        }
        for exception in exceptions
    ]


# ==========================================
# GET EXCEPTIONS FOR A SPECIFIC SHIPMENT
# ==========================================

@router.get("/shipments/{shipment_id}/exceptions")
def get_shipment_exceptions(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    exceptions = db.query(Exception).filter(
        Exception.shipment_id == shipment_id
    ).order_by(
        Exception.exception_id.desc()
    ).all()

    return [
        {
            "exception_id": exception.exception_id,
            "shipment_id": exception.shipment_id,
            "exception_type": exception.exception_type,
            "description": exception.description,
            "severity": exception.severity,
            "status": exception.status,
            "detected_at": exception.detected_at,
            "resolved_at": exception.resolved_at
        }
        for exception in exceptions
    ]
