from app.database.connection import SessionLocal
from app.models import Shipment

db = SessionLocal()

try:
    shipment = db.query(Shipment).filter(
        Shipment.shipment_id == 2
    ).first()

    if not shipment:
        raise ValueError("Shipment 2 not found")

    shipment.shipper = "Shanghai Pacific Trading Co Ltd"

    db.commit()

    print("Shipment 2 shipper corrected successfully.")
    print("New shipper:", shipment.shipper)

except Exception as error:
    db.rollback()
    print("Correction failed:", error)

finally:
    db.close()