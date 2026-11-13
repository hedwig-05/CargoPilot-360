from app.database.connection import SessionLocal
from app.engines.exception_lifecycle import get_active_exception


db = SessionLocal()

try:
    exception = get_active_exception(
        db=db,
        shipment_id=4,
        exception_type="DOCUMENT_MISMATCH"
    )

    if exception:
        print("ACTIVE EXCEPTION FOUND")
        print("Exception ID:", exception.exception_id)
        print("Shipment ID:", exception.shipment_id)
        print("Type:", exception.exception_type)
        print("Status:", exception.status)
        print("Description:", exception.description)

    else:
        print("No active exception found.")

finally:
    db.close()