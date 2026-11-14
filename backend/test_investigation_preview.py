import json
import uuid

from app.database.connection import SessionLocal
from app.models.agent_workflow import AgentWorkflow
from app.models.agent_run import AgentRun
from app.engines.investigation import investigate_exception


db = SessionLocal()

try:
    token = uuid.uuid4().hex

    workflow = AgentWorkflow(
        workflow_public_id=f"TEST-{token}",
        thread_id=f"test-{token}",
        shipment_id=7,
        exception_id=10,
        trigger_type="MANUAL",
        graph_name="cargopilot_investigation_test",
        status="RUNNING",
        current_node="INVESTIGATION"
    )

    db.add(workflow)
    db.flush()

    run = AgentRun(
        run_public_id=f"TEST-{token}",
        workflow_id=workflow.workflow_id,
        step_no=1,
        agent_type="INVESTIGATION",
        node_name="investigation",
        execution_status="PROCESSING"
    )

    db.add(run)
    db.flush()

    print("\nTemporary workflow ID:", workflow.workflow_id)
    print("Temporary investigation run ID:", run.run_id)

    result = investigate_exception(
        db=db,
        exception_id=10,
        workflow_id=workflow.workflow_id,
        run_id=run.run_id,
        commit=False
    )

    print("\n========== INVESTIGATION RESULT ==========")
    print(json.dumps(result, indent=4, default=str))

finally:
    db.rollback()
    db.close()

    print("\nDatabase transaction rolled back.")
    print("No test records were committed.")