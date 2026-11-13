
from app.database.connection import SessionLocal
from app.engines.document_validation import validate_shipment_documents


db = SessionLocal()

try:
    print("\n===== DOCUMENT VALIDATION TEST =====")

    result = validate_shipment_documents(
        db,
        shipment_id=4,
        commit=True
    )

    print("\nValidation Result:")
    print(result)

    print("\n===== TEST COMPLETED =====")

finally:
    db.rollback()
    db.close()
