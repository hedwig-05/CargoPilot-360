
from app.database.connection import SessionLocal
from app.models import Document, Shipment


db = SessionLocal()

try:
    shipments = db.query(Shipment).order_by(
        Shipment.shipment_id
    ).all()

    for shipment in shipments:

        print("\n" + "=" * 65)
        print("SHIPMENT:", shipment.shipment_ref)
        print("=" * 65)

        documents = db.query(Document).filter(
            Document.shipment_id == shipment.shipment_id
        ).order_by(Document.document_id).all()

        for document in documents:

            if document.document_type not in [
                "COMMERCIAL_INVOICE",
                "BILL_OF_LADING"
            ]:
                continue

            print("\nDocument ID:", document.document_id)
            print("Document Type:", document.document_type)
            print("File Name:", document.file_name)
            print("Extraction Status:", document.extraction_status)
            print("Validation Status:", document.validation_status)

            print("\nExtracted Fields:")

            fields = document.extracted_fields or {}

            for field, value in fields.items():
                print(f"  {field}: {value}")

            print("-" * 50)

finally:
    db.close()
