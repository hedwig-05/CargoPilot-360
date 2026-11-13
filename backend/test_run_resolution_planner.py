
from app.database.connection import SessionLocal
from app.engines.resolution_planner import create_resolution_plan


# ==================================================
# TEST RESOLUTION PLANNING ENGINE
# ==================================================

db = SessionLocal()

try:
    print("\n========================================")
    print("TESTING RESOLUTION PLANNING ENGINE")
    print("========================================")

    result = create_resolution_plan(
        db=db,
        exception_id=3,
        triggered_by=2
    )

    print("\nRESOLUTION PLAN CREATED SUCCESSFULLY")
    print("----------------------------------------")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n========================================")
    print("TEST COMPLETED")
    print("========================================")

except Exception as e:
    print("\nRESOLUTION PLANNING FAILED")
    print("----------------------------------------")
    print(f"Error: {e}")

finally:
    db.close()
