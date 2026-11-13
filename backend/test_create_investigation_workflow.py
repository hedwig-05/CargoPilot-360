import uuid

from app.database.connection import SessionLocal
from app.models import AgentWorkflow, AgentRun

db = SessionLocal()

try:
    # Create the investigation workflow
    workflow = AgentWorkflow(
        workflow_public_id="WF-" + uuid.uuid4().hex[:12].upper(),
        thread_id="THREAD-" + uuid.uuid4().hex[:12].upper(),
        shipment_id=3,
        exception_id=3,
        trigger_type="MANUAL",
        graph_name="cargopilot_main",
        status="RUNNING",
        current_node="INVESTIGATION"
    )

    db.add(workflow)
    db.flush()

    # Create the investigation agent run
    run = AgentRun(
        run_public_id="RUN-" + uuid.uuid4().hex[:12].upper(),
        workflow_id=workflow.workflow_id,
        step_no=1,
        agent_type="INVESTIGATION",
        node_name="INVESTIGATION",
        input_data={
            "exception_id": 3,
            "shipment_id": 3
        },
        execution_status="PROCESSING"
    )

    db.add(run)
    db.commit()

    print("WORKFLOW CREATED:", workflow.workflow_id)
    print("RUN CREATED:", run.run_id)

except Exception:
    db.rollback()
    raise

finally:
    db.close()