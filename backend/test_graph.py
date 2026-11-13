from app.agents.graph import cargo_graph


initial_state = {
    "shipment_id": 5,
    "shipment_reference": "CP-SHP-2026-005",

    "workflow_id": None,
    "supervisor_run_id": None,
    "monitoring_run_id": None,

    "current_stage": "START",
    "workflow_status": "PENDING",

    "detected_exceptions": [],
    "exception_details": [],
    "monitoring_results": {},

    "investigation_summary": None,
    "investigation_results": [],

    "risk_assessment_results": [],
    "resolution_results": [],

    "errors": []
}


# ==========================================
# EXECUTE GRAPH ONCE
# ==========================================

result = cargo_graph.invoke(initial_state)


# ==========================================
# DISPLAY RESULT
# ==========================================

print("\n========== CARGOPILOT GRAPH RESULT ==========")

for key, value in result.items():
    print(f"{key}: {value}")