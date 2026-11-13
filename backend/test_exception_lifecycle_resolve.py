
from app.database.connection import SessionLocal

from app.engines.exception_lifecycle import resolve_exception


db = SessionLocal()

try:
    print("\n========== TEST 1: BLOCK UNVERIFIED RESOLUTION ==========")

    try:
        resolve_exception(
            db=db,
            exception_id=4,
            resolution_notes="Test resolution",
            verified=False,
            commit=False
        )

    except ValueError as error:
        print("Correctly blocked:", error)

    print("\n========== TEST 2: RESOLVE IN TEST TRANSACTION ==========")

    result = resolve_exception(
        db=db,
        exception_id=4,
        resolution_notes="TEST ONLY: Resolution rollback verification.",
        verified=True,
        commit=False
    )

    print("Success:", result["success"])
    print("Exception ID:", result["exception_id"])
    print("Status:", result["status"])

    assert result["status"] == "RESOLVED"

    print("\nRESOLUTION TEST PASSED")

finally:
    print("\n========== ROLLING BACK TEST DATA ==========")
    db.rollback()
    db.close()
    print("Database transaction rolled back.")
