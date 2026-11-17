"""Manual persistence integration test with FK-safe cleanup.

Run explicitly against the configured test database:
    python test_exception_persistence.py
"""
from sqlalchemy import text

from app.database.connection import DB_NAME, SessionLocal
from app.models import Exception as ShipmentException
from app.engines.exception_lifecycle import (
    get_active_exception,
    create_or_update_exception,
)

TEST_SHIPMENT_ID = 1
TEST_EXCEPTION_TYPE = "STAKEHOLDER_RESPONSE_DELAY"
TEST_DESCRIPTION_PREFIX = "TEMPORARY PERSISTENCE TEST - CargoPilot 360"


def main():
    if not DB_NAME.lower().endswith("_test"):
        raise RuntimeError(
            f"Safety stop: persistence test requires a *_test database, got {DB_NAME!r}."
        )

    test_exception_id = None
    db = SessionLocal()
    print("\n========== EXCEPTION PERSISTENCE TEST ==========")

    try:
        existing = get_active_exception(db, TEST_SHIPMENT_ID, TEST_EXCEPTION_TYPE)
        if existing and (existing.description or "").startswith(TEST_DESCRIPTION_PREFIX):
            raise RuntimeError(
                "A previous temporary persistence-test exception still exists; "
                "clean it up before rerunning."
            )
        if existing:
            raise RuntimeError(
                "An active exception of this type already exists. "
                "Stopping to protect existing business data."
            )

        result = create_or_update_exception(
            db=db,
            shipment_id=TEST_SHIPMENT_ID,
            exception_type=TEST_EXCEPTION_TYPE,
            description=TEST_DESCRIPTION_PREFIX,
            severity="LOW",
            detected_by="TEST",
            commit=True,
        )
        test_exception_id = result["exception_id"]
        print("\nSTEP 1: Exception creation")
        print("Operation:", result["operation"])
        print("Exception ID:", test_exception_id)

        verify_db = SessionLocal()
        try:
            saved = verify_db.query(ShipmentException).filter(
                ShipmentException.exception_id == test_exception_id
            ).first()
            if saved is None:
                raise RuntimeError("Saved exception could not be found.")
            print("\nSTEP 2: Persistence verification")
            print("Record found:", True)
        finally:
            verify_db.close()

        result = create_or_update_exception(
            db=db,
            shipment_id=TEST_SHIPMENT_ID,
            exception_type=TEST_EXCEPTION_TYPE,
            description=TEST_DESCRIPTION_PREFIX + " - UPDATED",
            severity="LOW",
            detected_by="TEST",
            commit=True,
        )
        print("\nSTEP 3: Duplicate prevention")
        print("Second operation:", result["operation"])
        print("Same exception ID:", result["exception_id"] == test_exception_id)
        if result["operation"] != "UPDATED" or result["exception_id"] != test_exception_id:
            raise RuntimeError("Duplicate prevention did not update the original test row.")

        print("\nALL PERSISTENCE TESTS PASSED.")

    finally:
        db.close()
        if test_exception_id is not None:
            cleanup_db = SessionLocal()
            try:
                temporary = cleanup_db.query(ShipmentException).filter(
                    ShipmentException.exception_id == test_exception_id,
                    ShipmentException.shipment_id == TEST_SHIPMENT_ID,
                    ShipmentException.exception_type == TEST_EXCEPTION_TYPE,
                    ShipmentException.detected_by == "TEST",
                    ShipmentException.description.like(TEST_DESCRIPTION_PREFIX + "%"),
                ).first()
                if temporary is not None:
                    cleanup_db.execute(
                        text("DELETE FROM exception_status_history WHERE exception_id = :exception_id"),
                        {"exception_id": test_exception_id},
                    )
                    cleanup_db.delete(temporary)
                    cleanup_db.commit()
                    print("\nCLEANUP: Temporary exception and its status history removed.")
                else:
                    cleanup_db.rollback()
                    print("\nCLEANUP: No matching temporary exception found; no rows deleted.")
            except Exception:
                cleanup_db.rollback()
                raise
            finally:
                cleanup_db.close()


if __name__ == "__main__":
    main()
