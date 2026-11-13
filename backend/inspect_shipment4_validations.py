from app.database.connection import SessionLocal
from app.models.document_validation import DocumentValidation

db = SessionLocal()

try:
    records = db.query(DocumentValidation).filter(
        DocumentValidation.shipment_id == 4
    ).order_by(DocumentValidation.validation_id).all()

    print("\n===== SHIPMENT 4 ALL VALIDATION RECORDS =====")

    for record in records:
        print(
            "\nID:", record.validation_id,
            "| Document:", record.document_id,
            "| Compared with:", record.compared_document_id,
            "| Field:", record.field_name,
            "| Result:", record.validation_result,
            "| Extracted:", record.extracted_value,
            "| Expected:", record.expected_value
        )

finally:
    db.close()