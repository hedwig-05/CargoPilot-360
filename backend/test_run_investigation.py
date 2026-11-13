from datetime import datetime

from app.database.connection import SessionLocal
from app.models import AgentRun, AgentWorkflow

from app.engines.investigation import investigate_exception


db = SessionLocal()

try:
    # Run investigation for Exception 3
    result = investigate_exception(
        db=db,
        exception_id=3,
        workflow_id=18,
        run_id=18,
        commit=False
    )

    # Update AgentRun
    run = db.query(AgentRun).filter(
        AgentRun.run_id == 18
    ).first()

    run.output_data = result
    run.execution_status = "COMPLETED"
    run.completed_at = datetime.now()

    # Update AgentWorkflow
    workflow = db.query(AgentWorkflow).filter(
        AgentWorkflow.workflow_id == 18
    ).first()

    workflow.status = "COMPLETED"
    workflow.current_node = "INVESTIGATION_COMPLETED"
    workflow.completed_at = datetime.now()

    db.commit()

    print("\nINVESTIGATION COMPLETED SUCCESSFULLY")
    print("RESULT:", result)

except Exception as e:
    db.rollback()
    print("INVESTIGATION FAILED:", str(e))
    raise

finally:
    db.close()