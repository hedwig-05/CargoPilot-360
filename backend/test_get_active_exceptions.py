
from app.database.connection import SessionLocal

from app.engines.exception_lifecycle import (
    get_active_exceptions_for_shipment
)


db = SessionLocal()

try:
    exceptions = get_active_exceptions_for_shipment(
        db=db,
        shipment_id=4
    )

    print("\nACTIVE EXCEPTIONS FOR SHIPMENT 4")
    print("--------------------------------")

    for exception in exceptions:
        print("Exception ID:", exception.exception_id)
        print("Type:", exception.exception_type)
        print("Severity:", exception.severity)
        print("Status:", exception.status)
        print("Description:", exception.description)
        print("--------------------------------")

    print("Total active exceptions:", len(exceptions))

finally:
    db.close()
