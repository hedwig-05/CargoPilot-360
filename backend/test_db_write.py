"""Manual database write smoke test; transaction is rolled back on exit."""
from datetime import datetime
from app.database.connection import SessionLocal
from app.models import Shipment


def main():
    print("\n===== CARGOPILOT DATABASE WRITE TEST =====")
    try:
        with SessionLocal.begin() as db:
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
                current_risk_level="LOW",
            )
            db.add(test_shipment)
            db.flush()
            test_id = test_shipment.shipment_id
            print("\n1. INSERT SUCCESSFUL! Temporary Shipment ID:", test_id)
            retrieved = db.query(Shipment).filter_by(shipment_id=test_id).first()
            if retrieved is None:
                raise RuntimeError("Could not retrieve inserted shipment!")
            print("\n2. READ SUCCESSFUL!")
            print("Reference:", retrieved.shipment_ref)
            print("Origin:", retrieved.origin)
            print("Destination:", retrieved.destination)
            db.delete(retrieved)
            db.flush()
            if db.get(Shipment, test_id) is not None:
                raise RuntimeError("Temporary shipment still exists!")
            print("\n3. DELETE SUCCESSFUL! Temporary shipment removed.")
        print("\n===== ALL DATABASE WRITE TESTS PASSED =====")
    except Exception as e:
        print("\nDATABASE WRITE TEST FAILED!")
        print("Error:", e)
        print("Transaction rolled back.")
        raise


if __name__ == "__main__":
    main()
