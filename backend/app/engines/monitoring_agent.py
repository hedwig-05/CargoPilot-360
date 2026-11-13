
import uuid
import time

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Shipment,
    AgentWorkflow,
    AgentRun
)

from app.engines.exception_detection import (
    detect_shipment_delays,
    detect_missing_documents
)


# ==================================================
# GENERATE PUBLIC IDS
# ==================================================

def generate_public_id(prefix: str):
    """
    Generate a unique public identifier.
    """

    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


# ==================================================
# MONITORING AGENT
# ==================================================

def run_monitoring_cycle(
    db: Session,
    triggered_by: int = None,
    shipment_id: int = None
):
    """
    Run a monitoring cycle across active shipments.

    If shipment_id is provided, only that shipment
    will be monitored.

    Otherwise, all active shipments will be monitored.

    For each active shipment:

    1. Create an AgentWorkflow.
    2. Create a Monitoring AgentRun.
    3. Detect overdue shipment milestones.
    4. Detect missing required documents.
    5. Save detection results.
    6. Complete or fail the workflow and run.

    Each shipment is processed independently.
    """

    cycle_started = time.perf_counter()

    # ------------------------------------------------
    # STEP 1: FIND ACTIVE SHIPMENTS
    # ------------------------------------------------

    query = db.query(Shipment).filter(
        Shipment.status.notin_(
            ["DELIVERED", "CANCELLED"]
        )
    )

    # If a shipment ID is provided, monitor only
    # that specific shipment.

    if shipment_id is not None:
        query = query.filter(
            Shipment.shipment_id == shipment_id
        )

    active_shipments = (
        query
        .order_by(Shipment.shipment_id)
        .all()
    )

    # Store basic values before processing.
    # This avoids relying on ORM objects after rollback.

    shipments_to_monitor = [
        {
            "shipment_id": shipment.shipment_id,
            "shipment_ref": shipment.shipment_ref
        }
        for shipment in active_shipments
    ]

    cycle_results = []

    # ------------------------------------------------
    # STEP 2: PROCESS EACH SHIPMENT
    # ------------------------------------------------

    for shipment_data in shipments_to_monitor:

        shipment_id = shipment_data["shipment_id"]
        shipment_ref = shipment_data["shipment_ref"]

        workflow_public_id = generate_public_id("WF")
        thread_id = generate_public_id("THREAD")
        run_public_id = generate_public_id("RUN")

        shipment_started = time.perf_counter()

        workflow = None
        agent_run = None

        try:

            # ----------------------------------------
            # STEP 2A: CREATE WORKFLOW
            # ----------------------------------------

            workflow = AgentWorkflow(
                workflow_public_id=workflow_public_id,
                thread_id=thread_id,
                shipment_id=shipment_id,
                trigger_type="MONITORING_CYCLE",
                trigger_ref="MANUAL_MONITORING_CYCLE",
                graph_name="cargopilot_main",
                status="RUNNING",
                current_node="MONITORING",
                triggered_by=triggered_by
            )

            db.add(workflow)
            db.flush()

            # ----------------------------------------
            # STEP 2B: CREATE AGENT RUN
            # ----------------------------------------

            agent_run = AgentRun(
                run_public_id=run_public_id,
                workflow_id=workflow.workflow_id,
                parent_run_id=None,
                step_no=1,
                agent_type="MONITORING",
                node_name="monitoring",
                input_data={
                    "shipment_id": shipment_id,
                    "shipment_ref": shipment_ref,
                    "trigger_type": "MONITORING_CYCLE"
                },
                execution_status="PROCESSING"
            )

            db.add(agent_run)

            # Commit workflow and run BEFORE
            # executing detection operations.
            #
            # This preserves execution history even
            # if a detection operation subsequently fails.

            db.commit()

            db.refresh(workflow)
            db.refresh(agent_run)

            # ----------------------------------------
            # STEP 2C: DETECT SHIPMENT DELAYS
            # ----------------------------------------

            delay_result = detect_shipment_delays(
                db=db,
                commit=False,
                shipment_id=shipment_id
            )

            # ----------------------------------------
            # STEP 2D: DETECT MISSING DOCUMENTS
            # ----------------------------------------

            document_result = detect_missing_documents(
                db=db,
                commit=False,
                shipment_id=shipment_id
            )

            # ----------------------------------------
            # STEP 2E: BUILD OUTPUT
            # ----------------------------------------

            output_data = {
                "shipment_id": shipment_id,
                "shipment_ref": shipment_ref,
                "monitoring_results": {
                    "shipment_delay_detection": delay_result,
                    "missing_document_detection": document_result
                },
                "monitoring_completed_at": (
                    datetime.now().isoformat()
                )
            }

            latency_ms = int(
                (time.perf_counter() - shipment_started) * 1000
            )

            # ----------------------------------------
            # STEP 2F: COMPLETE WORKFLOW AND RUN
            # ----------------------------------------

            workflow.status = "COMPLETED"
            workflow.current_node = "MONITORING_COMPLETED"
            workflow.completed_at = datetime.now()

            agent_run.output_data = output_data
            agent_run.execution_status = "COMPLETED"
            agent_run.latency_ms = latency_ms
            agent_run.completed_at = datetime.now()

            # Commit exception changes and execution
            # results together.

            db.commit()

            cycle_results.append({
                "shipment_id": shipment_id,
                "shipment_ref": shipment_ref,
                "workflow_public_id": workflow_public_id,
                "run_public_id": run_public_id,
                "status": "COMPLETED",
                "delay_detection": delay_result,
                "missing_document_detection": document_result
            })

        except Exception as error:

            # ----------------------------------------
            # STEP 2G: HANDLE FAILURE
            # ----------------------------------------

            db.rollback()

            error_message = str(error)

            # Retrieve the previously committed records.

            failed_workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_public_id
                    == workflow_public_id
                )
                .first()
            )

            failed_run = (
                db.query(AgentRun)
                .filter(
                    AgentRun.run_public_id == run_public_id
                )
                .first()
            )

            # Preserve failure information.

            if failed_workflow and failed_run:

                failed_workflow.status = "FAILED"
                failed_workflow.current_node = "MONITORING_FAILED"
                failed_workflow.error_message = error_message
                failed_workflow.completed_at = datetime.now()

                failed_run.execution_status = "FAILED"
                failed_run.error_message = error_message
                failed_run.latency_ms = int(
                    (time.perf_counter() - shipment_started) * 1000
                )
                failed_run.completed_at = datetime.now()

                db.commit()

            cycle_results.append({
                "shipment_id": shipment_id,
                "shipment_ref": shipment_ref,
                "workflow_public_id": workflow_public_id,
                "run_public_id": run_public_id,
                "status": "FAILED",
                "error": error_message
            })

    # ------------------------------------------------
    # STEP 3: BUILD CYCLE SUMMARY
    # ------------------------------------------------

    completed_count = sum(
        1 for result in cycle_results
        if result["status"] == "COMPLETED"
    )

    failed_count = sum(
        1 for result in cycle_results
        if result["status"] == "FAILED"
    )

    cycle_latency_ms = int(
        (time.perf_counter() - cycle_started) * 1000
    )

    return {
        "message": "Monitoring cycle completed",
        "shipments_found": len(shipments_to_monitor),
        "shipments_completed": completed_count,
        "shipments_failed": failed_count,
        "cycle_latency_ms": cycle_latency_ms,
        "results": cycle_results
    }
