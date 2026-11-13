
from app.database.connection import SessionLocal
from app.models import Shipment

db = SessionLocal()

try:
    shipments = db.query(Shipment).order_by(
        Shipment.shipment_id
    ).all()

    print("\n===== ALL SHIPMENT MASTER RECORDS =====")

    for shipment in shipments:
        print("\nShipment:", shipment.shipment_ref)
        print("Container:", shipment.container_no)
        print("Shipper:", shipment.shipper)
        print("Consignee:", shipment.consignee)

finally:
    db.close()
