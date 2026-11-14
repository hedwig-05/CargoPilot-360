
import traceback

from app.agents.graph import cargo_graph


# ==========================================
# INITIALIZE CARGOPILOT GRAPH STATE
# ==========================================

initial_state = {
    "shipment_id": 7,
    "shipment_reference": "CP-TEST-2026-001",

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

    "llm_analysis_results": [],

    "risk_assessment_results": [],
    "resolution_results": [],

    "errors": []
}


# ==========================================
# EXECUTE CARGOPILOT GRAPH
# ==========================================

def main():

    print("\n==========================================")
    print("       CARGOPILOT 360 GRAPH TEST")
    print("==========================================")

    print("\nShipment ID:", initial_state["shipment_id"])
    print("Shipment Reference:", initial_state["shipment_reference"])

    print("\nStarting graph execution...\n")

    try:

        result = cargo_graph.invoke(initial_state)

        # ======================================
        # DISPLAY FINAL GRAPH RESULT
        # ======================================

        print("\n==========================================")
        print("       CARGOPILOT GRAPH RESULT")
        print("==========================================")

        for key, value in result.items():

            print(f"\n{key}:")
            print(value)

        # ======================================
        # DISPLAY EXECUTION SUMMARY
        # ======================================

        print("\n==========================================")
        print("       EXECUTION SUMMARY")
        print("==========================================")

        print("Shipment:", result.get("shipment_reference"))
        print("Final Stage:", result.get("current_stage"))
        print("Workflow Status:", result.get("workflow_status"))

        print(
            "Detected Exceptions:",
            len(result.get("detected_exceptions", []))
        )

        print(
            "Investigation Results:",
            len(result.get("investigation_results", []))
        )

        print(
            "LLM Analysis Results:",
            len(result.get("llm_analysis_results", []))
        )

        print(
            "Risk Assessment Results:",
            len(result.get("risk_assessment_results", []))
        )

        print(
            "Resolution Results:",
            len(result.get("resolution_results", []))
        )

        print("Errors:", result.get("errors", []))

        print("\n==========================================")
        print("       GRAPH EXECUTION FINISHED")
        print("==========================================")

    except Exception as error:

        print("\n==========================================")
        print("       GRAPH EXECUTION FAILED")
        print("==========================================")

        print("Error:", str(error))

        traceback.print_exc()


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    main()
