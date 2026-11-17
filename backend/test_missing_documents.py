"""Manual missing-document detection utility."""
from app.database.connection import SessionLocal
from app.engines.exception_detection import detect_missing_documents


def main():
    db = SessionLocal()
    try:
        result = detect_missing_documents(db)
        print("\n===== MISSING DOCUMENT DETECTION RESULT =====")
        print(result)
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
