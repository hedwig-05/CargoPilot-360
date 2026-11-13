
from app.database.connection import SessionLocal
from app.models import Shipment

db = SessionLocal()

try:
    shipment = db.query(Shipment).filter(
        Shipment.shipment_id == 1
    ).first()

    if shipment:
        print("\n===== SHIPMENT MASTER RECORD =====")

        print("Shipment ID:", shipment.shipment_id)
        print("Shipment Ref:", shipment.shipment_ref)
        print("Container No:", shipment.container_no)
        print("Shipper:", shipment.shipper)
        print("Consignee:", shipment.consignee)
        print("Origin:", shipment.origin)
        print("Destination:", shipment.destination)

    else:
        print("Shipment not found.")

finally:
    db.close()
