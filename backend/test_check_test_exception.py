
from app.database.connection import SessionLocal

from app.engines.exception_lifecycle import get_active_exception


db = SessionLocal()

try:
    exception = get_active_exception(
        db=db,
        shipment_id=1,
        exception_type="STAKEHOLDER_RESPONSE_DELAY"
    )

    if exception:
        print("An active test exception already exists.")
        print("Exception ID:", exception.exception_id)
        print("Status:", exception.status)
    else:
        print("SAFE TO USE: No active test exception exists.")

finally:
    db.close()
