from app.database.connection import SessionLocal
from app.models import Shipment

corrections = {
    1: {
        "container_no": "TGHU1234567",
        "shipper": "Lion City Exports Pte Ltd",
        "consignee": "Lanka Retail Imports (Pvt) Ltd"
    },
    2: {
        "container_no": "MSCU7654321",
        "shipper": "Shanghai Pacific TradingCo Ltd",
        "consignee": "Serendib Distributors (Pvt) Ltd"
    },
    3: {
        "container_no": "GESU2345678",
        "shipper": "Gulf Star General Trading LLC",
        "consignee": "Ceylon Industrial Supplies (Pvt) Ltd"
    },
    4: {
        "container_no": "INBU3456789",
        "shipper": "Western India Exports Pvt Ltd",
        "consignee": "Islandwide Merchants (Pvt) Ltd"
    },
    5: {
        "container_no": "CMAU4567890",
        "shipper": "North Sea Cargo BV",
        "consignee": "Lanka Engineering Solutions (Pvt) Ltd"
    }
}

db = SessionLocal()

try:
    print("\n===== SHIPMENT MASTER CORRECTION =====")

    for shipment_id, values in corrections.items():
        shipment = db.query(Shipment).filter(
            Shipment.shipment_id == shipment_id
        ).first()

        if not shipment:
            raise ValueError(f"Shipment {shipment_id} not found")

        shipment.container_no = values["container_no"]
        shipment.shipper = values["shipper"]
        shipment.consignee = values["consignee"]

        print(f"\nUpdated: {shipment.shipment_ref}")
        print("Container:", shipment.container_no)
        print("Shipper:", shipment.shipper)
        print("Consignee:", shipment.consignee)

    db.commit()

    print("\nAll five shipment records successfully updated.")

except Exception as error:
    db.rollback()
    print("\nCorrection failed. Changes rolled back.")
    print("Error:", error)

finally:
    db.close()