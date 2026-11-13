
from app.database.connection import SessionLocal
from app.engines.document_validation import validate_shipment_documents


def main():

    db = SessionLocal()

    try:

        print("\n======================================")
        print(" CARGOPILOT DOCUMENT VALIDATION")
        print(" COMMIT MODE")
        print("======================================")

        shipment_id = 7

        print(f"\nShipment ID: {shipment_id}")
        print("Running document validation...\n")

        result = validate_shipment_documents(
            db=db,
            shipment_id=shipment_id,
            commit=True
        )

        print("\n========== VALIDATION RESULT ==========")
        print(result)

        print("\n======================================")
        print(" VALIDATION COMMITTED")
        print("======================================")

    except Exception as e:

        db.rollback()

        print("\nVALIDATION FAILED:")
        print(str(e))

    finally:

        db.close()


if __name__ == "__main__":
    main()
