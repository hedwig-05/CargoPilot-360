
from app.database.connection import SessionLocal
from app.models import Shipment

print("\n===== CARGOPILOT DATABASE READ TEST =====")

try:
    with SessionLocal() as db:

        shipments = db.query(Shipment).all()

        print(f"\nTotal shipments found: {len(shipments)}")

        for shipment in shipments:
            print("\n-------------------------")
            print("Shipment ID:", shipment.shipment_id)
            print("Reference:", shipment.shipment_ref)
            print("Origin:", shipment.origin)
            print("Destination:", shipment.destination)
            print("Status:", shipment.status)

    print("\nDatabase read successful!")

except Exception as e:
    print("\nDatabase read failed!")
    print("Error:", e)
