"""Manual resolution-planning engine test; may write a plan."""
from app.database.connection import SessionLocal
from app.engines.resolution_planner import create_resolution_plan


def main():
    db = SessionLocal()
    try:
        print("\n========================================")
        print("TESTING RESOLUTION PLANNING ENGINE")
        print("========================================")
        result = create_resolution_plan(db=db, exception_id=3, triggered_by=2)
        print("\nRESOLUTION PLAN RESULT")
        print("----------------------------------------")
        for key, value in result.items():
            print(f"{key}: {value}")
        print("\n========================================")
        print("TEST COMPLETED")
        print("========================================")
    except Exception as e:
        db.rollback()
        print("\nRESOLUTION PLANNING FAILED")
        print(type(e).__name__, str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
