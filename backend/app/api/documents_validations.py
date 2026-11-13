
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import DocumentValidation


router = APIRouter(
    prefix="/api/shipments",
    tags=["Document Validations"]
)


# ==========================================
# GET DOCUMENT VALIDATIONS FOR A SHIPMENT
# ==========================================

@router.get("/{shipment_id}/validations")
def get_shipment_validations(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    validations = db.query(DocumentValidation).filter(
        DocumentValidation.shipment_id == shipment_id
    ).order_by(
        DocumentValidation.validation_id.asc()
    ).all()

    return [
        {
            "validation_id": validation.validation_id,
            "document_id": validation.document_id,
            "compared_document_id": validation.compared_document_id,
            "shipment_id": validation.shipment_id,
            "validation_run_id": validation.validation_run_id,
            "field_name": validation.field_name,
            "extracted_value": validation.extracted_value,
            "expected_value": validation.expected_value,
            "validation_result": validation.validation_result,
            "explanation": validation.explanation,
            "validated_at": validation.validated_at
        }
        for validation in validations
    ]
