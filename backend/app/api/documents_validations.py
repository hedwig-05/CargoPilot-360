from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, aliased

from app.database.connection import get_db
from app.models import Document, DocumentValidation


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

    compared_document = aliased(Document)

    validation_rows = db.query(
        DocumentValidation,
        Document,
        compared_document
    ).join(
        Document,
        Document.document_id == DocumentValidation.document_id
    ).outerjoin(
        compared_document,
        compared_document.document_id == DocumentValidation.compared_document_id
    ).filter(
        DocumentValidation.shipment_id == shipment_id
    ).order_by(
        DocumentValidation.validation_id.asc()
    ).all()

    return [
        {
            "validation_id": validation.validation_id,
            "document_id": validation.document_id,
            "document_type": document.document_type,
            "file_name": document.file_name,
            "compared_document_id": validation.compared_document_id,
            "compared_document_type": (
                compared.document_type if compared else None
            ),
            "compared_file_name": (
                compared.file_name if compared else None
            ),
            "shipment_id": validation.shipment_id,
            "validation_run_id": validation.validation_run_id,
            "field_name": validation.field_name,
            "extracted_value": validation.extracted_value,
            "expected_value": validation.expected_value,
            "validation_result": validation.validation_result,
            "explanation": validation.explanation,
            "validated_at": validation.validated_at
        }
        for validation, document, compared in validation_rows
    ]
