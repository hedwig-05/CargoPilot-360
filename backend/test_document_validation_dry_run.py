
from app.database.connection import SessionLocal
from app.engines.document_validation import validate_shipment_documents


def main():

    db = SessionLocal()

    try:
        print("\n======================================")
        print(" CARGOPILOT DOCUMENT VALIDATION TEST")
        print("======================================")

        shipment_id = 7

        print(f"\nTesting shipment ID: {shipment_id}")
        print("Running validation in DRY-RUN mode...\n")

        result = validate_shipment_documents(
            db=db,
            shipment_id=shipment_id,
            commit=False
        )

        print("\n========== VALIDATION RESULT ==========")

        print(result)

        print("\n======================================")
        print("Rolling back test database changes...")
        print("======================================")

        db.rollback()

        print("\nDRY-RUN COMPLETED.")
        print("No validation changes were committed.")

    except Exception as e:

        db.rollback()

        print("\nVALIDATION TEST FAILED:")
        print(str(e))

    finally:
        db.close()


if __name__ == "__main__":
    main()
