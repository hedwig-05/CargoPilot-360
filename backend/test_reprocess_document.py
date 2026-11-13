
from app.database.connection import SessionLocal
from app.engines.document_processing import process_document


def main():

    db = SessionLocal()

    try:

        document_id = 12

        print("\n======================================")
        print(" CARGOPILOT DOCUMENT REPROCESSING")
        print("======================================")

        print(f"\nReprocessing Document ID: {document_id}")

        result = process_document(
            db=db,
            document_id=document_id
        )

        print("\n========== PROCESSING RESULT ==========")

        print("Message:", result["message"])
        print("Document ID:", result["document_id"])
        print("File:", result["file_name"])
        print("Extraction Status:", result["extraction_status"])
        print("Fields Found:", result["fields_found"])

        print("\n========== CORRECTED FIELDS ==========")

        for field, value in result["extracted_fields"].items():
            print(f"{field}: {value}")

        print("\n========== IMPORTANT FIELD CHECK ==========")

        fields = result["extracted_fields"]

        print("Shipper:", fields.get("shipper"))
        print("Consignee:", fields.get("consignee"))

        print("\nDOCUMENT REPROCESSING COMPLETED.")

    except Exception as e:

        db.rollback()

        print("\nDOCUMENT REPROCESSING FAILED:")
        print(str(e))

    finally:

        db.close()


if __name__ == "__main__":
    main()
