
from app.database.connection import SessionLocal
from app.engines.document_processing import process_document


db = SessionLocal()

try:
    result = process_document(db, 2)

    print("\n===== DOCUMENT PROCESSING RESULT =====")

    for key, value in result.items():
        print(f"{key}: {value}")

except Exception as e:
    print("ERROR:", e)

finally:
    db.close()
