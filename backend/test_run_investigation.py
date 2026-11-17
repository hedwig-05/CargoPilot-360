"""Manual investigation runner for the legacy sample workflow IDs."""
from datetime import datetime
from app.database.connection import SessionLocal
from app.models import AgentRun, AgentWorkflow
from app.engines.investigation import investigate_exception


def main():
    db = SessionLocal()
    try:
        result = investigate_exception(
            db=db, exception_id=3, workflow_id=18, run_id=18, commit=False
        )
        run = db.query(AgentRun).filter(AgentRun.run_id == 18).first()
        workflow = db.query(AgentWorkflow).filter(AgentWorkflow.workflow_id == 18).first()
        if run is None or workflow is None:
            raise RuntimeError("Legacy workflow/run 18 was not found; refusing to continue.")
        run.output_data = result
        run.execution_status = "COMPLETED"
        run.completed_at = datetime.now()
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


if __name__ == "__main__":
    main()
