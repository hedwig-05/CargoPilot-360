import uuid
from datetime import datetime

from sqlalchemy import func

from langgraph.graph import StateGraph, START, END

from app.agents.state import CargoPilotState

from app.database.connection import SessionLocal

from app.models import (
    Shipment,
    Exception as ShipmentException,
    AgentWorkflow,
    AgentRun,
    ResolutionPlan,
    Action
)

from app.engines.exception_detection import (
    detect_shipment_delays,
    detect_missing_documents
)

from app.engines.investigation import investigate_exception

from app.engines.risk_assessment import assess_shipment_risk

from app.engines.resolution_planner import create_resolution_plan

from app.llm.router import create_llm_router


# ==========================================================
# HELPER: UPDATE AGENT RUN
# ==========================================================

def update_agent_run(
    db,
    run_id,
    status,
    output_data=None,
    error_message=None
):

    if not run_id:
        return

    run = db.query(AgentRun).filter(
        AgentRun.run_id == run_id
    ).first()

    if not run:
        return

    run.execution_status = status

    if output_data is not None:
        run.output_data = output_data

    if error_message:
        run.error_message = error_message

    if status in ["COMPLETED", "FAILED", "SKIPPED"]:
        run.completed_at = datetime.now()


# ==========================================================
# HELPER: CREATE NEXT CHILD RUN
# ==========================================================

def create_child_run(
    db,
    workflow_id,
    parent_run_id,
    agent_type,
    node_name,
    input_data
):

    current_max_step = (
        db.query(func.max(AgentRun.step_no))
        .filter(
            AgentRun.workflow_id == workflow_id
        )
        .scalar()
    ) or 0

    run = AgentRun(
        run_public_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        parent_run_id=parent_run_id,
        step_no=current_max_step + 1,
        agent_type=agent_type,
        node_name=node_name,
        execution_status="PROCESSING",
        input_data=input_data
    )

    db.add(run)
    db.flush()

    return run


# ==========================================================
# MONITORING NODE
# ==========================================================

def monitoring_node(state: CargoPilotState):

    print("\n========== MONITORING NODE STARTED ==========")

    db = SessionLocal()

    workflow_id = None
    supervisor_run_id = None
    monitoring_run_id = None

    try:

        shipment_id = state["shipment_id"]

        # ------------------------------------------
        # 1. CREATE WORKFLOW
        # ------------------------------------------

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == shipment_id
            )
            .first()
        )

        if not shipment:
            raise ValueError(
                f"Shipment {shipment_id} was not found."
            )

        if shipment.status == "CANCELLED":
            raise ValueError(
                "Cannot execute workflow for a cancelled shipment."
            )

        workflow = AgentWorkflow(
            workflow_public_id=str(uuid.uuid4()),
            thread_id=str(uuid.uuid4()),
            shipment_id=shipment_id,
            trigger_type="MANUAL",
            trigger_ref="LANGGRAPH_MANUAL_EXECUTION",
            graph_name="cargopilot_main",
            status="RUNNING",
            current_node="monitoring"
        )

        db.add(workflow)
        db.flush()

        workflow_id = workflow.workflow_id

        # ------------------------------------------
        # 2. CREATE SUPERVISOR RUN
        # ------------------------------------------

        supervisor_run = AgentRun(
            run_public_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            parent_run_id=None,
            step_no=1,
            agent_type="SUPERVISOR",
            node_name="supervisor",
            execution_status="PROCESSING",
            input_data={
                "shipment_id": shipment_id,
                "shipment_reference": state["shipment_reference"]
            }
        )

        db.add(supervisor_run)
        db.flush()

        supervisor_run_id = supervisor_run.run_id

        # ------------------------------------------
        # 3. CREATE MONITORING RUN
        # ------------------------------------------

        monitoring_run = AgentRun(
            run_public_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            parent_run_id=supervisor_run_id,
            step_no=2,
            agent_type="MONITORING",
            node_name="monitoring",
            execution_status="PROCESSING",
            input_data={
                "shipment_id": shipment_id
            }
        )

        db.add(monitoring_run)
        db.flush()

        monitoring_run_id = monitoring_run.run_id

        db.commit()

        # ------------------------------------------
        # 4. DETECT DELAYS
        # ------------------------------------------

        print("\nChecking shipment delays...")

        delay_result = detect_shipment_delays(
            db=db,
            commit=False,
            shipment_id=shipment_id
        )

        # ------------------------------------------
        # 5. DETECT MISSING DOCUMENTS
        # ------------------------------------------

        print("\nChecking missing documents...")

        document_result = detect_missing_documents(
            db=db,
            commit=False,
            shipment_id=shipment_id
        )

        # ------------------------------------------
        # 6. RETRIEVE ACTIVE EXCEPTIONS
        # ------------------------------------------

        exceptions = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.shipment_id == shipment_id,
                ShipmentException.status.notin_(
                    ["RESOLVED", "CLOSED"]
                )
            )
            .order_by(
                ShipmentException.exception_id
            )
            .all()
        )

        exception_details = [
            {
                "exception_id": item.exception_id,
                "shipment_id": item.shipment_id,
                "exception_type": item.exception_type,
                "description": item.description,
                "severity": item.severity,
                "status": item.status
            }
            for item in exceptions
        ]

        detected_exceptions = sorted({
            item["exception_type"]
            for item in exception_details
        })

        monitoring_results = {
            "shipment_delay_detection": delay_result,
            "missing_document_detection": document_result
        }

        # ------------------------------------------
        # 7. COMPLETE MONITORING RUN
        # ------------------------------------------

        update_agent_run(
            db,
            monitoring_run_id,
            "COMPLETED",
            output_data={
                "detected_exceptions": detected_exceptions,
                "exception_details": exception_details,
                "monitoring_results": monitoring_results
            }
        )

        db.commit()

        print("\nMonitoring completed.")

        return {
            "workflow_id": workflow_id,
            "supervisor_run_id": supervisor_run_id,
            "monitoring_run_id": monitoring_run_id,
            "current_stage": "MONITORING",
            "workflow_status": "RUNNING",
            "detected_exceptions": detected_exceptions,
            "exception_details": exception_details,
            "monitoring_results": monitoring_results,
            "investigation_results": [],
            "llm_analysis_results": [],
            "risk_assessment_results": [],
            "resolution_results": [],
            "errors": []
        }

    except Exception as error:

        db.rollback()

        print("\nMonitoring failed:", str(error))

        try:

            update_agent_run(
                db,
                monitoring_run_id,
                "FAILED",
                error_message=str(error)
            )

            update_agent_run(
                db,
                supervisor_run_id,
                "FAILED",
                error_message=str(error)
            )

            workflow = (
                db.query(AgentWorkflow)
                .filter(
                    AgentWorkflow.workflow_id == workflow_id
                )
                .first()
            ) if workflow_id else None

            if workflow:
                workflow.status = "FAILED"
                workflow.error_message = str(error)

            db.commit()

        except Exception:
            db.rollback()

        return {
            "workflow_id": workflow_id,
            "supervisor_run_id": supervisor_run_id,
            "monitoring_run_id": monitoring_run_id,
            "current_stage": "MONITORING_FAILED",
            "workflow_status": "FAILED",
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# INVESTIGATION NODE
# ==========================================================

def investigation_node(state: CargoPilotState):

    print("\n========== INVESTIGATION NODE STARTED ==========")

    db = SessionLocal()

    investigation_results = []

    try:

        workflow_id = state["workflow_id"]
        supervisor_run_id = state["supervisor_run_id"]

        exception_details = state["exception_details"]

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        if workflow:
            workflow.current_node = "investigation"

        db.commit()

        for exception_data in exception_details:

            exception_id = exception_data["exception_id"]

            print(
                f"\nInvestigating exception ID: {exception_id}"
            )

            investigation_run = create_child_run(
                db=db,
                workflow_id=workflow_id,
                parent_run_id=supervisor_run_id,
                agent_type="INVESTIGATION",
                node_name="investigation",
                input_data={
                    "exception_id": exception_id,
                    "shipment_id": exception_data["shipment_id"],
                    "exception_type": exception_data["exception_type"]
                }
            )

            db.commit()
            db.refresh(investigation_run)

            try:

                result = investigate_exception(
                    db=db,
                    exception_id=exception_id,
                    workflow_id=workflow_id,
                    run_id=investigation_run.run_id,
                    commit=True
                )

                update_agent_run(
                    db,
                    investigation_run.run_id,
                    "COMPLETED",
                    output_data=result
                )

                db.commit()

                investigation_results.append(result)

            except Exception as error:

                db.rollback()

                update_agent_run(
                    db,
                    investigation_run.run_id,
                    "FAILED",
                    error_message=str(error)
                )

                db.commit()

                raise

        summaries = [
            item.get("summary", "Investigation completed")
            for item in investigation_results
        ]

        return {
            "current_stage": "INVESTIGATION",
            "workflow_status": "RUNNING",
            "investigation_summary": " | ".join(summaries),
            "investigation_results": investigation_results
        }

    except Exception as error:

        db.rollback()

        print("\nInvestigation failed:", str(error))

        return {
            "current_stage": "INVESTIGATION_FAILED",
            "workflow_status": "FAILED",
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# LLM INVESTIGATION ANALYSIS NODE
# ==========================================================

def llm_analysis_node(state: CargoPilotState):

    print("\n========== LLM ANALYSIS NODE STARTED ==========")

    db = SessionLocal()

    analysis_results = []
    router = None

    try:

        workflow_id = state["workflow_id"]
        supervisor_run_id = state["supervisor_run_id"]

        investigation_results = state.get(
            "investigation_results", []
        )

        exception_details = state.get(
            "exception_details", []
        )

        # Update the workflow's current node.

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        if workflow:
            workflow.current_node = "llm_analysis"

        db.commit()

        for investigation in investigation_results:

            exception_id = investigation["exception_id"]

            # Find corresponding exception information.

            exception_data = next(
                (
                    item for item in exception_details
                    if item["exception_id"] == exception_id
                ),
                {}
            )

            # Prepare verified investigation findings.

            evidence = {
                "exception": exception_data,
                "investigation_findings": {
                    "summary": investigation.get("summary"),
                    "possible_cause": investigation.get(
                        "possible_cause"
                    ),
                    "affected_process": investigation.get(
                        "affected_process"
                    ),
                    "recommended_next": investigation.get(
                        "recommended_next"
                    ),
                    "evidence_count": investigation.get(
                        "evidence_count"
                    )
                }
            }

            prompt = f"""
You are the investigation analysis assistant
for CargoPilot 360, a logistics operations system.

Analyze the following verified investigation findings.

INVESTIGATION DATA:
{evidence}

INSTRUCTIONS:

1. Summarize the operational problem.
2. Explain the possible cause identified by the
   investigation engine.
3. Explain the operational impact that can reasonably
   be inferred from the supplied information.
4. Recommend two practical next steps.

IMPORTANT RULES:

- Use only the information supplied.
- Do not invent shipment events, dates, locations,
  authorities, people or document details.
- A possible cause is not a confirmed cause.
- Clearly distinguish confirmed facts from possibilities.
- If information is insufficient, say so.
- Do not approve or execute any action.
- Keep the response concise and professional.
"""

            print(
                f"\nAnalyzing investigation for exception "
                f"{exception_id}..."
            )

            # ------------------------------------------
            # 1. CREATE DEDICATED LLM AGENT RUN
            # ------------------------------------------

            llm_run = create_child_run(
                db=db,
                workflow_id=workflow_id,
                parent_run_id=supervisor_run_id,
                agent_type="LLM",
                node_name="llm_analysis",
                input_data={
                    "exception_id": exception_id,
                    "shipment_id": exception_data.get(
                        "shipment_id"
                    ),
                    "prompt_version": "investigation-analysis-v1",
                    "investigation_findings": evidence
                }
            )

            db.commit()
            db.refresh(llm_run)

            llm_run_id = llm_run.run_id

            # ------------------------------------------
            # 2. CALL LLM ROUTER AND RECORD METADATA
            # ------------------------------------------

            try:

                if router is None:
                    router = create_llm_router()

                result = router.generate_with_metadata(prompt)

                # --------------------------------------
                # 3. SAVE SUCCESSFUL LLM EXECUTION
                # --------------------------------------

                llm_run.provider_name = result["provider_name"]

                llm_run.model_name = result["model_name"]

                llm_run.latency_ms = result["latency_ms"]

                llm_run.prompt_version = (
                    "investigation-analysis-v1"
                )

                llm_run.execution_status = "COMPLETED"

                llm_run.output_data = {
                    "analysis": result["content"],
                    "provider_name": result["provider_name"],
                    "model_name": result["model_name"],
                    "latency_ms": result["latency_ms"],
                    "fallback_used": result["fallback_used"]
                }

                llm_run.completed_at = datetime.now()

                db.commit()

                # --------------------------------------
                # 4. ADD RESULT TO LANGGRAPH STATE
                # --------------------------------------

                analysis_results.append({
                    "exception_id": exception_id,
                    "llm_run_id": llm_run_id,
                    "provider_status": "SUCCESS",
                    "provider_name": result["provider_name"],
                    "model_name": result["model_name"],
                    "latency_ms": result["latency_ms"],
                    "fallback_used": result["fallback_used"],
                    "analysis": result["content"]
                })

                print(
                    f"LLM run {llm_run_id} completed "
                    f"using {result['provider_name']}."
                )

            except Exception as error:

                print(
                    f"LLM execution failed for exception "
                    f"{exception_id}: {error}"
                )

                # --------------------------------------
                # 5. RECORD FAILED LLM EXECUTION
                # --------------------------------------

                db.rollback()

                failed_run = (
                    db.query(AgentRun)
                    .filter(
                        AgentRun.run_id == llm_run_id
                    )
                    .first()
                )

                if failed_run:

                    failed_run.execution_status = "FAILED"

                    failed_run.error_message = str(error)

                    failed_run.output_data = {
                        "error": str(error)
                    }

                    failed_run.completed_at = datetime.now()

                    db.commit()

                analysis_results.append({
                    "exception_id": exception_id,
                    "llm_run_id": llm_run_id,
                    "provider_status": "FAILED",
                    "analysis": None,
                    "error": str(error)
                })

        print("\nLLM analysis completed.")

        return {
            "current_stage": "LLM_ANALYSIS",
            "llm_analysis_results": analysis_results
        }

    except Exception as error:

        db.rollback()

        print("\nLLM analysis node failed:", str(error))

        return {
            "current_stage": "LLM_ANALYSIS",
            "llm_analysis_results": analysis_results,
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# RISK ASSESSMENT NODE
# ==========================================================

def risk_assessment_node(state: CargoPilotState):

    print("\n========== RISK ASSESSMENT NODE STARTED ==========")

    db = SessionLocal()
    risk_results = []

    try:

        workflow_id = state["workflow_id"]
        supervisor_run_id = state["supervisor_run_id"]
        shipment_id = state["shipment_id"]

        # Collect all relevant exception IDs for traceability.

        exception_ids = [
            item["exception_id"]
            for item in state["exception_details"]
        ]

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        if workflow:
            workflow.current_node = "risk_assessment"

        db.commit()

        print(
            f"\nAssessing shipment ID: {shipment_id}"
        )

        print(
            f"Related exception IDs: {exception_ids}"
        )

        # Create ONE risk assessment agent run
        # because risk assessment is shipment-level.

        risk_run = create_child_run(
            db=db,
            workflow_id=workflow_id,
            parent_run_id=supervisor_run_id,
            agent_type="RISK_ASSESSMENT",
            node_name="risk_assessment",
            input_data={
                "shipment_id": shipment_id,
                "exception_ids": exception_ids
            }
        )

        db.commit()
        db.refresh(risk_run)

        try:

            result = assess_shipment_risk(
                db=db,
                shipment_id=shipment_id,
                exception_id=None,
                workflow_id=workflow_id,
                run_id=risk_run.run_id
            )

            run_output = {
                "risk_id": result["risk_id"],
                "shipment_id": shipment_id,
                "related_exception_ids": exception_ids,
                "risk_score": float(result["risk_score"]),
                "risk_level": result["risk_level"],
                "ruleset_version": result["ruleset_version"],
                "explanation": result["explanation"]
            }

            update_agent_run(
                db,
                risk_run.run_id,
                "COMPLETED",
                output_data=run_output
            )

            db.commit()

            risk_results.append(run_output)

        except Exception as error:

            db.rollback()

            update_agent_run(
                db,
                risk_run.run_id,
                "FAILED",
                error_message=str(error)
            )

            db.commit()

            raise

        return {
            "current_stage": "RISK_ASSESSMENT",
            "workflow_status": "RUNNING",
            "risk_assessment_results": risk_results
        }

    except Exception as error:

        db.rollback()

        print("\nRisk assessment failed:", str(error))

        return {
            "current_stage": "RISK_ASSESSMENT_FAILED",
            "workflow_status": "FAILED",
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# DECISION NODE
# ==========================================================

def decision_node(state: CargoPilotState):

    print("\n========== DECISION NODE STARTED ==========")

    db = SessionLocal()

    resolution_results = []

    try:

        workflow_id = state["workflow_id"]
        supervisor_run_id = state["supervisor_run_id"]

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        )

        if workflow:
            workflow.current_node = "decision"

        db.commit()

        for exception_data in state["exception_details"]:

            exception_id = exception_data["exception_id"]

            print(
                f"\nCreating resolution plan for exception "
                f"{exception_id}"
            )

            # ------------------------------------------
            # 1. CHECK FOR AN EXISTING ACTIVE PLAN
            # ------------------------------------------

            existing_plan = (
                db.query(ResolutionPlan)
                .filter(
                    ResolutionPlan.exception_id == exception_id,
                    ResolutionPlan.status.in_([
                        "DRAFT",
                        "PENDING_APPROVAL",
                        "APPROVED",
                        "EXECUTING"
                    ])
                )
                .order_by(
                    ResolutionPlan.plan_id.desc()
                )
                .first()
            )

            # ------------------------------------------
            # 2. REUSE EXISTING PLAN IF AVAILABLE
            # ------------------------------------------

            if existing_plan:

                print(
                    f"Reusing existing resolution plan: "
                    f"{existing_plan.plan_id}"
                )

                # Link this workflow to the workflow
                # that owns the existing resolution plan.
                # Prevent a workflow from becoming its own parent.

                if existing_plan.workflow_id != workflow_id:

                    workflow.parent_workflow_id = (
                        existing_plan.workflow_id
                    )

                    print(
                        f"DEPENDENCY LINK: Workflow {workflow_id} "
                        f"depends on workflow {existing_plan.workflow_id}"
                    )

                else:

                    print(
                        "Existing plan belongs to this workflow. "
                        "No parent dependency required."
                    )

                existing_action = (
                    db.query(Action)
                    .filter(
                        Action.plan_id == existing_plan.plan_id
                    )
                    .order_by(
                        Action.action_id.desc()
                    )
                    .first()
                )

                if not existing_action:
                    raise ValueError(
                        f"Active plan {existing_plan.plan_id} "
                        "has no associated action."
                    )

                # Record this reuse decision as an AgentRun.

                decision_run = create_child_run(
                    db=db,
                    workflow_id=workflow_id,
                    parent_run_id=supervisor_run_id,
                    agent_type="DECISION",
                    node_name="resolution_planner_reuse",
                    input_data={
                        "exception_id": exception_id,
                        "existing_plan_id": existing_plan.plan_id,
                        "existing_action_id": existing_action.action_id
                    }
                )

                db.commit()

                update_agent_run(
                    db,
                    decision_run.run_id,
                    "COMPLETED",
                    output_data={
                        "decision": "REUSE_EXISTING_PLAN",
                        "plan_id": existing_plan.plan_id,
                        "action_id": existing_action.action_id
                    }
                )

                db.commit()

                resolution_results.append({
                    "message": "Existing resolution plan reused.",
                    "exception_id": exception_id,
                    "workflow_id": existing_plan.workflow_id,
                    "run_id": decision_run.run_id,
                    "plan_id": existing_plan.plan_id,
                    "action_id": existing_action.action_id,
                    "version_no": existing_plan.version_no,
                    "priority": existing_plan.priority,
                    "plan_status": existing_plan.status,
                    "action_type": existing_action.action_type,
                    "approval_status": existing_action.approval_status,
                    "execution_status": existing_action.execution_status,
                    "reused_existing": True
                })

            # ------------------------------------------
            # 3. CREATE A NEW PLAN IF NONE EXISTS
            # ------------------------------------------

            else:

                result = create_resolution_plan(
                    db=db,
                    exception_id=exception_id
                )

                result["reused_existing"] = False

                resolution_results.append(result)

        return {
            "current_stage": "DECISION",
            "workflow_status": "WAITING_FOR_APPROVAL",
            "resolution_results": resolution_results
        }

    except Exception as error:

        db.rollback()

        print("\nDecision node failed:", str(error))

        return {
            "current_stage": "DECISION_FAILED",
            "workflow_status": "FAILED",
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# ROUTING
# ==========================================================

def route_after_monitoring(state: CargoPilotState):

    if state["workflow_status"] == "FAILED":
        return "finish"

    if state["detected_exceptions"]:
        return "investigate"

    return "finish"


def route_after_investigation(state: CargoPilotState):

    if state["workflow_status"] == "FAILED":
        return "finish"

    return "llm_analysis"


def route_after_risk_assessment(state: CargoPilotState):

    if state["workflow_status"] == "FAILED":
        return "finish"

    return "decision"


# ==========================================================
# FINISH NODE
# ==========================================================

def finish_node(state: CargoPilotState):

    print("\n========== WORKFLOW FINISHED ==========")

    db = SessionLocal()

    try:

        workflow_id = state.get("workflow_id")
        supervisor_run_id = state.get("supervisor_run_id")

        workflow_status = state.get("workflow_status")

        if workflow_status == "FAILED":
            final_status = "FAILED"

        elif workflow_status == "WAITING_FOR_APPROVAL":
            final_status = "WAITING_FOR_APPROVAL"

        else:
            final_status = "COMPLETED"

        # ------------------------------------------
        # UPDATE SUPERVISOR RUN
        # ------------------------------------------

        update_agent_run(
            db,
            supervisor_run_id,
            final_status,
            output_data={
                "current_stage": state["current_stage"],
                "detected_exceptions": state["detected_exceptions"],
                "investigation_summary": state.get(
                    "investigation_summary"
                ),
                "llm_analysis_results": state.get(
                    "llm_analysis_results", []
                ),
                "risk_assessment_results": state.get(
                    "risk_assessment_results", []
                ),
                "resolution_results": state.get(
                    "resolution_results", []
                ),
                "errors": state.get("errors", [])
            },
            error_message=(
                "; ".join(state.get("errors", []))
                if final_status == "FAILED" else None
            )
        )

        # ------------------------------------------
        # UPDATE WORKFLOW
        # ------------------------------------------

        workflow = (
            db.query(AgentWorkflow)
            .filter(
                AgentWorkflow.workflow_id == workflow_id
            )
            .first()
        ) if workflow_id else None

        if workflow:

            workflow.status = final_status

            if final_status == "WAITING_FOR_APPROVAL":

                workflow.current_node = "WAITING_FOR_APPROVAL"

                # Workflow is awaiting human input.
                # Do not set completed_at yet.

            else:

                workflow.current_node = "finish"
                workflow.completed_at = datetime.now()

            if final_status == "FAILED":

                workflow.error_message = "; ".join(
                    state.get("errors", [])
                )

        db.commit()

        print("Final workflow status:", final_status)

        return {
            "current_stage": final_status,
            "workflow_status": final_status
        }

    except Exception as error:

        db.rollback()

        print(
            "Could not update workflow tracking:",
            str(error)
        )

        return {
            "current_stage": "FAILED",
            "workflow_status": "FAILED",
            "errors": state.get("errors", []) + [str(error)]
        }

    finally:
        db.close()


# ==========================================================
# BUILD GRAPH
# ==========================================================

builder = StateGraph(CargoPilotState)

builder.add_node("monitoring", monitoring_node)

builder.add_node("investigation", investigation_node)

builder.add_node("llm_analysis", llm_analysis_node)

builder.add_node("risk_assessment", risk_assessment_node)

builder.add_node("decision", decision_node)

builder.add_node("finish", finish_node)


# ==========================================================
# GRAPH CONNECTIONS
# ==========================================================

builder.add_edge(START, "monitoring")

builder.add_conditional_edges(
    "monitoring",
    route_after_monitoring,
    {
        "investigate": "investigation",
        "finish": "finish"
    }
)

builder.add_conditional_edges(
    "investigation",
    route_after_investigation,
    {
        "llm_analysis": "llm_analysis",
        "finish": "finish"
    }
)

builder.add_edge("llm_analysis", "risk_assessment")

builder.add_conditional_edges(
    "risk_assessment",
    route_after_risk_assessment,
    {
        "decision": "decision",
        "finish": "finish"
    }
)

builder.add_edge("decision", "finish")

builder.add_edge("finish", END)


# ==========================================================
# COMPILE GRAPH
# ==========================================================

cargo_graph = builder.compile()