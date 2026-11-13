from typing import TypedDict, Optional, List


class CargoPilotState(TypedDict):

    # Shipment information
    shipment_id: Optional[int]
    shipment_reference: Optional[str]

    # Workflow tracking
    workflow_id: Optional[int]
    supervisor_run_id: Optional[int]
    monitoring_run_id: Optional[int]

    # Workflow status
    current_stage: str
    workflow_status: str

    # Monitoring results
    detected_exceptions: List[str]
    exception_details: List[dict]
    monitoring_results: dict

    # Investigation results
    investigation_summary: Optional[str]
    investigation_results: List[dict]

    # Risk assessment results
    risk_assessment_results: List[dict]

    # Decision results
    resolution_results: List[dict]

    # Error tracking
    errors: List[str]