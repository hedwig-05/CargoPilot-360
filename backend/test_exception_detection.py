
from app.database.connection import SessionLocal
from app.engines.exception_detection import detect_shipment_delays


db = SessionLocal()

try:
    result = detect_shipment_delays(db)

    print("\n===== SHIPMENT DELAY DETECTION RESULT =====")
    print(result)

except Exception as e:
    db.rollback()
    print("ERROR:", e)

finally:
    db.close()
