"""Manual monitoring-cycle integration test. Writes workflow/run records."""
from app.database.connection import SessionLocal
from app.engines.monitoring_agent import run_monitoring_cycle


def main():
    db = SessionLocal()
    try:
        print("\n====================================")
        print(" CARGOPILOT 360 - MONITORING TEST")
        print("====================================\n")
        result = run_monitoring_cycle(db=db, triggered_by=4)
        print("\nMONITORING CYCLE RESULT:\n")
        print(result)
        print("\n====================================")
        print(" MONITORING TEST FINISHED")
        print("====================================")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
