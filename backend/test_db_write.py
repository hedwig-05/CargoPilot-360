
from datetime import datetime
from app.database.connection import SessionLocal
from app.models import Shipment

print("\n===== CARGOPILOT DATABASE WRITE TEST =====")

test_shipment = None

try:
    with SessionLocal.begin() as db:

        # 1. INSERT a temporary shipment
        test_shipment = Shipment(
            shipment_ref="CP-TEST-" + datetime.now().strftime("%Y%m%d%H%M%S"),
            origin="Singapore",
            destination="Colombo, Sri Lanka",
            shipper="Test Shipper",
            consignee="Test Consignee",
            container_type="40FT",
            expected_arrival=datetime(2026, 12, 1, 12, 0),
            status="BOOKED",
            current_risk_score=0.00,
            current_risk_level="LOW"
        )

        db.add(test_shipment)
        db.flush()

        test_id = test_shipment.shipment_id

        print("\n1. INSERT SUCCESSFUL!")
        print("Temporary Shipment ID:", test_id)

        # 2. READ the inserted shipment
        retrieved = db.query(Shipment).filter_by(
            shipment_id=test_id
        ).first()

        if retrieved:
            print("\n2. READ SUCCESSFUL!")
            print("Reference:", retrieved.shipment_ref)
            print("Origin:", retrieved.origin)
            print("Destination:", retrieved.destination)
        else:
            raise Exception("Could not retrieve inserted shipment!")

        # 3. DELETE the temporary shipment
        db.delete(retrieved)
        db.flush()

        print("\n3. DELETE SUCCESSFUL!")

        # Confirm it no longer exists in this transaction
        remaining = db.get(Shipment, test_id)

        if remaining is None:
            print("Temporary shipment successfully removed!")
        else:
            raise Exception("Temporary shipment still exists!")

    print("\n===== ALL DATABASE WRITE TESTS PASSED =====")

except Exception as e:
    print("\nDATABASE WRITE TEST FAILED!")
    print("Error:", e)
    print("Transaction rolled back.")
