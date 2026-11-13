
from app.database.connection import SessionLocal

from app.engines.exception_lifecycle import (
    create_or_update_exception
)


db = SessionLocal()

try:
    print("\n========== TEST 1: CREATE EXCEPTION ==========")

    result = create_or_update_exception(
        db=db,
        shipment_id=1,
        exception_type="STAKEHOLDER_RESPONSE_DELAY",
        description="TEST: Stakeholder has not responded to a shipment inquiry.",
        severity="MEDIUM",
        detected_by="LIFECYCLE_TEST",
        commit=False
    )

    print("Operation:", result["operation"])
    print("Exception ID:", result["exception_id"])
    print("Description:", result["exception"].description)
    print("Severity:", result["exception"].severity)

    assert result["operation"] == "CREATED"
    assert result["exception_id"] is not None

    print("\nCREATE TEST PASSED")

    print("\n========== TEST 2: UPDATE EXCEPTION ==========")

    result = create_or_update_exception(
        db=db,
        shipment_id=1,
        exception_type="STAKEHOLDER_RESPONSE_DELAY",
        description="TEST: Updated description after a follow-up attempt.",
        severity="HIGH",
        detected_by="LIFECYCLE_TEST",
        commit=False
    )

    print("Operation:", result["operation"])
    print("Exception ID:", result["exception_id"])
    print("Updated description:", result["exception"].description)
    print("Updated severity:", result["exception"].severity)

    assert result["operation"] == "UPDATED"
    assert result["exception"].severity == "HIGH"

    print("\nUPDATE TEST PASSED")

finally:
    print("\n========== ROLLING BACK TEST DATA ==========")
    db.rollback()
    db.close()
    print("Database transaction rolled back.")
