
from app.database.connection import SessionLocal
from app.engines.exception_lifecycle import (
    create_or_update_exception,
    get_active_exception
)

db = SessionLocal()

try:
    print("\nTEST 1: UPDATE EXISTING OPEN EXCEPTION")
    print("======================================")

    result = create_or_update_exception(
        db=db,
        shipment_id=2,
        exception_type="SHIPMENT_DELAY",
        description="Temporary test description for Shipment 2.",
        severity="HIGH",
        commit=False
    )

    print("Operation:", result["operation"])
    print("Exception ID:", result["exception_id"])
    print("Expected: UPDATED")

    print("\nTEST 2: SKIP INVESTIGATING EXCEPTION")
    print("====================================")

    existing = get_active_exception(
        db=db,
        shipment_id=4,
        exception_type="DOCUMENT_MISMATCH"
    )

    if not existing:
        print("ERROR: Expected active exception was not found.")
    else:
        original_description = existing.description
        original_severity = existing.severity

        result = create_or_update_exception(
            db=db,
            shipment_id=4,
            exception_type="DOCUMENT_MISMATCH",
            description="This description must NOT replace the investigation.",
            severity="LOW",
            commit=False
        )

        print("Operation:", result["operation"])
        print("Exception ID:", result["exception_id"])
        print("Original status:", existing.status)
        print(
            "Description preserved:",
            existing.description == original_description
        )
        print(
            "Severity preserved:",
            existing.severity == original_severity
        )
        print("Expected: SKIPPED")

    print("\nTEST 3: CREATE NEW EXCEPTION")
    print("============================")

    existing = get_active_exception(
        db=db,
        shipment_id=1,
        exception_type="STAKEHOLDER_RESPONSE_DELAY"
    )

    if existing:
        print("SKIPPED TEST: An active test exception already exists.")
    else:
        result = create_or_update_exception(
            db=db,
            shipment_id=1,
            exception_type="STAKEHOLDER_RESPONSE_DELAY",
            description="Temporary lifecycle creation test.",
            severity="MEDIUM",
            commit=False
        )

        print("Operation:", result["operation"])
        print("Exception ID:", result["exception_id"])
        print("Expected: CREATED")

finally:
    db.rollback()
    db.close()

    print("\nROLLBACK COMPLETE")
    print("No test changes were permanently saved.")
