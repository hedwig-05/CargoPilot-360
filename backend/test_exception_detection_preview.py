
from app.database.connection import SessionLocal

from app.engines.exception_detection import (
    detect_shipment_delays,
    detect_missing_documents
)

db = SessionLocal()

try:
    print("\n==========================================")
    print(" CARGOPILOT 360 - EXCEPTION DETECTION PREVIEW")
    print("==========================================")

    # ------------------------------------------
    # 1. SHIPMENT DELAY DETECTION
    # ------------------------------------------

    print("\n1. SHIPMENT DELAY DETECTION")
    print("------------------------------------------")

    delay_result = detect_shipment_delays(
        db,
        commit=False
    )

    for key, value in delay_result.items():
        print(f"{key}: {value}")

    # ------------------------------------------
    # 2. MISSING DOCUMENT DETECTION
    # ------------------------------------------

    print("\n2. MISSING DOCUMENT DETECTION")
    print("------------------------------------------")

    document_result = detect_missing_documents(
        db,
        commit=False
    )

    for key, value in document_result.items():
        print(f"{key}: {value}")

    # ------------------------------------------
    # 3. ROLLBACK
    # ------------------------------------------

    print("\n3. DATABASE ROLLBACK")
    print("------------------------------------------")

    db.rollback()

    print("ROLLBACK COMPLETE")
    print("No test changes were permanently saved.")

except Exception as error:
    db.rollback()
    print("\nTEST FAILED:", error)
    raise

finally:
    db.close()
