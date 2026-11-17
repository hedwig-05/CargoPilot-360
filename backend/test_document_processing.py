"""Manual single-document processing utility."""
from app.database.connection import SessionLocal
from app.engines.document_processing import process_document


def main():
    db = SessionLocal()
    try:
        result = process_document(db, 2)
        print("\n===== DOCUMENT PROCESSING RESULT =====")
        for key, value in result.items():
            print(f"{key}: {value}")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
