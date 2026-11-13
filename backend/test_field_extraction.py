
from app.database.connection import SessionLocal
from app.models import Document

from app.engines.document_field_extraction import (
    extract_document_fields
)


def main():

    db = SessionLocal()

    try:

        document = (
            db.query(Document)
            .filter(Document.document_id == 12)
            .first()
        )

        if not document:
            print("Document 12 not found.")
            return

        result = extract_document_fields(
            document.extracted_text,
            document.document_type
        )

        print("\n========== FIELD EXTRACTION TEST ==========")

        print("\nDocument:", document.file_name)

        print("\nExtracted fields:")

        for field, value in result["extracted_fields"].items():
            print(f"{field}: {value}")

        print("\nTotal fields:", result["fields_found"])

        print("\n========== IMPORTANT FIELDS ==========")

        print(
            "Shipper:",
            result["extracted_fields"].get("shipper")
        )

        print(
            "Consignee:",
            result["extracted_fields"].get("consignee")
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
