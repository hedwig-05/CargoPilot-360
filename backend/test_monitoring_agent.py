
from app.database.connection import SessionLocal

from app.engines.monitoring_agent import run_monitoring_cycle


db = SessionLocal()

try:

    print("\n====================================")
    print(" CARGOPILOT 360 - MONITORING TEST")
    print("====================================\n")

    result = run_monitoring_cycle(
        db=db,
        triggered_by=4
    )

    print("\nMONITORING CYCLE RESULT:\n")

    print(result)

    print("\n====================================")
    print(" MONITORING TEST FINISHED")
    print("====================================")

finally:
    db.close()
