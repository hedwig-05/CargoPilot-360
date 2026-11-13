from app.database.connection import SessionLocal
from app.models.exception import Exception

db = SessionLocal()

try:
    exceptions = db.query(Exception).filter(
        Exception.shipment_id == 3,
        Exception.exception_type == "MISSING_DOCUMENT"
    ).all()

    print("\n===== SHIPMENT 3 MISSING DOCUMENT EXCEPTIONS =====")

    print("Total exceptions:", len(exceptions))

    for exception in exceptions:
        print("\nException ID:", exception.exception_id)
        print("Type:", exception.exception_type)
        print("Status:", exception.status)
        print("Description:", exception.description)

finally:
    db.close()