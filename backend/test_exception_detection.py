"""Manual shipment-delay detection utility."""
from app.database.connection import SessionLocal
from app.engines.exception_detection import detect_shipment_delays


def main():
    db = SessionLocal()
    try:
        result = detect_shipment_delays(db)
        print("\n===== SHIPMENT DELAY DETECTION RESULT =====")
        print(result)
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
