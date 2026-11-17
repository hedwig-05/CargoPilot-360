"""Manual exception-detection preview; transaction is rolled back."""
from app.database.connection import SessionLocal
from app.engines.exception_detection import detect_shipment_delays, detect_missing_documents


def main():
    db = SessionLocal()
    try:
        print("\n==========================================")
        print(" CARGOPILOT 360 - EXCEPTION DETECTION PREVIEW")
        print("==========================================")
        print("\n1. SHIPMENT DELAY DETECTION")
        delay_result = detect_shipment_delays(db, commit=False)
        for key, value in delay_result.items():
            print(f"{key}: {value}")
        print("\n2. MISSING DOCUMENT DETECTION")
        document_result = detect_missing_documents(db, commit=False)
        for key, value in document_result.items():
            print(f"{key}: {value}")
        db.rollback()
        print("\nROLLBACK COMPLETE")
        print("No test changes were permanently saved.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
