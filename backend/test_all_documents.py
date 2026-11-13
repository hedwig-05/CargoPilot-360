
from app.database.connection import SessionLocal
from app.engines.document_processing import process_all_documents


db = SessionLocal()

try:
    result = process_all_documents(db)

    print("\n===== BULK DOCUMENT PROCESSING RESULT =====")

    print("Message:", result["message"])
    print("Total Documents:", result["total_documents"])
    print("Successful:", result["successful"])
    print("Failed:", result["failed"])

    print("\n===== INDIVIDUAL DOCUMENT RESULTS =====")

    for item in result["results"]:
        print(item)

except Exception as e:
    db.rollback()
    print("ERROR:", e)

finally:
    db.close()
