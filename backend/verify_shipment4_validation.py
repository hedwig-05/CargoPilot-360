
from app.database.connection import SessionLocal
from app.models.document_validation import DocumentValidation
from app.models.document import Document
from app.models.exception import Exception

db = SessionLocal()

try:
    print("\n===== SHIPMENT 4 VALIDATION VERIFICATION =====")

    validations = db.query(DocumentValidation).filter(
        DocumentValidation.shipment_id == 4
    ).all()

    print("\nTotal validation records:", len(validations))

    counts = {}
    for validation in validations:
        result = validation.validation_result
        counts[result] = counts.get(result, 0) + 1

    print("Validation counts:", counts)

    documents = db.query(Document).filter(
        Document.shipment_id == 4
    ).all()

    print("\nDocument statuses:")
    for document in documents:
        print(document.document_type, ":", document.validation_status)

    exceptions = db.query(Exception).filter(
        Exception.shipment_id == 4,
        Exception.exception_type == "DOCUMENT_MISMATCH"
    ).all()

    print("\nDocument mismatch exceptions:", len(exceptions))

    for exception in exceptions:
        print("Exception ID:", exception.exception_id)
        print("Severity:", exception.severity)
        print("Status:", exception.status)
        print("Description:", exception.description)

finally:
    db.close()