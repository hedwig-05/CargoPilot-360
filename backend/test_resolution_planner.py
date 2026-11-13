
from app.database.connection import SessionLocal
from app.engines.resolution_planner import create_resolution_plan

db = SessionLocal()

try:
    result = create_resolution_plan(
        db=db,
        exception_id=3,
        triggered_by=1
    )

    print("\n========== RESOLUTION PLANNER TEST ==========")
    print(result)
    print("=============================================")

except Exception as e:
    db.rollback()
    print("\nRESOLUTION PLANNER TEST FAILED")
    print(type(e).__name__, str(e))

finally:
    db.close()
