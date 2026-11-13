
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import RiskAssessment
from app.api.helpers import serialize_records, get_all_records
from app.engines.risk_assessment import assess_shipment_risk
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/api",
    tags=["Risk Assessments"]
)


# GET ALL RISK ASSESSMENTS

@router.get("/risk-assessments")
def get_all_risk_assessments(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, RiskAssessment)

    return serialize_records(records, RiskAssessment)


# GET RISK ASSESSMENTS FOR A SHIPMENT

@router.get("/shipments/{shipment_id}/risk-assessments")
def get_shipment_risk_assessments(
    shipment_id: int,
    db: Session = Depends(get_db)
):
    records = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.shipment_id == shipment_id)
        .order_by(RiskAssessment.assessed_at.desc())
        .all()
    )

    return serialize_records(records, RiskAssessment)


# CALCULATE SHIPMENT RISK

@router.post("/shipments/{shipment_id}/risk-assessments/calculate")
def calculate_shipment_risk(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        result = assess_shipment_risk(
            db=db,
            shipment_id=shipment_id
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Risk assessment failed."
        )
