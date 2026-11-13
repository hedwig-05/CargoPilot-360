
from app.database.connection import SessionLocal
from app.models import Exception as ShipmentException

db = SessionLocal()

active_statuses = [
    "OPEN",
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE"
]

try:
    print("\nEXISTING SHIPMENT DELAY EXCEPTIONS")
    print("===================================")

    for shipment_id in [2, 5]:

        exceptions = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.shipment_id == shipment_id,
                ShipmentException.exception_type == "SHIPMENT_DELAY",
                ShipmentException.status.in_(active_statuses)
            )
            .all()
        )

        print(f"\nShipment ID: {shipment_id}")

        if not exceptions:
            print("No active SHIPMENT_DELAY exception found.")

        for exception in exceptions:
            print("Exception ID:", exception.exception_id)
            print("Status:", exception.status)
            print("Severity:", exception.severity)
            print("Description:", exception.description)

finally:
    db.rollback()
    db.close()
