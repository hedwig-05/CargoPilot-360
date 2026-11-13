
from app.database.connection import SessionLocal
from app.models import Exception as ShipmentException

db = SessionLocal()

try:
    print("\n========== EXCEPTION VERIFICATION ==========")

    exceptions = (
        db.query(ShipmentException)
        .filter(
            ShipmentException.exception_type.in_([
                "SHIPMENT_DELAY",
                "MISSING_DOCUMENT"
            ])
        )
        .order_by(ShipmentException.exception_id)
        .all()
    )

    for exception in exceptions:
        print("\nException ID:", exception.exception_id)
        print("Shipment ID:", exception.shipment_id)
        print("Type:", exception.exception_type)
        print("Status:", exception.status)
        print("Severity:", exception.severity)
        print("Description:", exception.description)
        print("------------------------------------------")

    print("\nTotal exceptions:", len(exceptions))

finally:
    db.close()
