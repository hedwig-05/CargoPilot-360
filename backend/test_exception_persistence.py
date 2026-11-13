
from app.database.connection import SessionLocal
from app.models import Exception as ShipmentException
from app.engines.exception_lifecycle import (
    get_active_exception,
    create_or_update_exception
)

TEST_SHIPMENT_ID = 1
TEST_EXCEPTION_TYPE = "STAKEHOLDER_RESPONSE_DELAY"

test_exception_id = None

print("\n========== EXCEPTION PERSISTENCE TEST ==========")

try:
    # STEP 1: Check that no test exception already exists
    db = SessionLocal()

    existing = get_active_exception(
        db,
        TEST_SHIPMENT_ID,
        TEST_EXCEPTION_TYPE
    )

    if existing:
        raise RuntimeError(
            "A test exception already exists. "
            "Stopping to protect existing database records."
        )

    print("\nSTEP 1: No existing test exception found.")

    # STEP 2: Create and permanently save a test exception
    result = create_or_update_exception(
        db=db,
        shipment_id=TEST_SHIPMENT_ID,
        exception_type=TEST_EXCEPTION_TYPE,
        description="TEMPORARY PERSISTENCE TEST - CargoPilot 360",
        severity="LOW",
        detected_by="TEST",
        commit=True
    )

    test_exception_id = result["exception_id"]

    print("\nSTEP 2: Exception creation")
    print("Operation:", result["operation"])
    print("Exception ID:", test_exception_id)

    # STEP 3: Verify persistence using a separate database session
    verify_db = SessionLocal()

    try:
        saved = (
            verify_db.query(ShipmentException)
            .filter(
                ShipmentException.exception_id == test_exception_id
            )
            .first()
        )

        print("\nSTEP 3: Persistence verification")
        print("Record found:", saved is not None)

        if not saved:
            raise RuntimeError("Saved exception could not be found.")

    finally:
        verify_db.close()

    # STEP 4: Call the helper again with the same shipment and type
    result = create_or_update_exception(
        db=db,
        shipment_id=TEST_SHIPMENT_ID,
        exception_type=TEST_EXCEPTION_TYPE,
        description="TEMPORARY PERSISTENCE TEST - UPDATED",
        severity="LOW",
        detected_by="TEST",
        commit=True
    )

    print("\nSTEP 4: Duplicate prevention")
    print("Second operation:", result["operation"])
    print("Same exception ID:", result["exception_id"] == test_exception_id)

    if result["operation"] != "UPDATED":
        raise RuntimeError("Expected the second call to update the existing exception.")

    # STEP 5: Confirm that only one active exception exists
    verify_db = SessionLocal()

    try:
        count = (
            verify_db.query(ShipmentException)
            .filter(
                ShipmentException.shipment_id == TEST_SHIPMENT_ID,
                ShipmentException.exception_type == TEST_EXCEPTION_TYPE,
                ShipmentException.status.in_([
                    "OPEN",
                    "INVESTIGATING",
                    "AWAITING_APPROVAL",
                    "IN_PROGRESS",
                    "AWAITING_RESPONSE"
                ])
            )
            .count()
        )

        print("\nSTEP 5: Active exception count:", count)

        if count != 1:
            raise RuntimeError("Expected exactly one active test exception.")

    finally:
        verify_db.close()

    print("\nALL PERSISTENCE TESTS PASSED.")

except Exception as error:
    print("\nTEST FAILED:", error)
    raise

finally:
    db.close()

    # STEP 6: Remove only the temporary record created by this test
    if test_exception_id is not None:
        cleanup_db = SessionLocal()

        try:
            temporary_record = (
                cleanup_db.query(ShipmentException)
                .filter(
                    ShipmentException.exception_id == test_exception_id
                )
                .first()
            )

            if temporary_record:
                cleanup_db.delete(temporary_record)
                cleanup_db.commit()
                print("\nSTEP 6: Temporary test record cleaned up.")
            else:
                print("\nSTEP 6: Temporary record was already absent.")

        except Exception as cleanup_error:
            cleanup_db.rollback()
            print("\nCLEANUP WARNING:", cleanup_error)
            print("Please check the temporary exception manually.")

        finally:
            cleanup_db.close()
