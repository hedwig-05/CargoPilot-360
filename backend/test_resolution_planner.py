"""Manual resolution-planner integration test; may persist a plan."""
from app.database.connection import SessionLocal
from app.engines.resolution_planner import create_resolution_plan


def main():
    db = SessionLocal()
    try:
        result = create_resolution_plan(db=db, exception_id=3, triggered_by=1)
        print("\n========== RESOLUTION PLANNER TEST ==========")
        print(result)
        print("=============================================")
    except Exception as e:
        db.rollback()
        print("\nRESOLUTION PLANNER TEST FAILED")
        print(type(e).__name__, str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
