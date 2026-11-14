import unittest

from app.agents.graph import (
    route_after_investigation,
    route_after_monitoring,
    route_after_risk_assessment,
)


class AgentGraphRoutingRegressionTests(unittest.TestCase):

    def test_failed_monitoring_routes_to_finish(self):
        state = {
            "workflow_status": "FAILED",
            "detected_exceptions": ["DOCUMENT_MISMATCH"],
        }
        self.assertEqual(route_after_monitoring(state), "finish")

    def test_monitoring_with_exceptions_routes_to_investigation(self):
        state = {
            "workflow_status": "RUNNING",
            "detected_exceptions": ["DOCUMENT_MISMATCH"],
        }
        self.assertEqual(route_after_monitoring(state), "investigate")

    def test_monitoring_without_exceptions_routes_to_finish(self):
        state = {
            "workflow_status": "RUNNING",
            "detected_exceptions": [],
        }
        self.assertEqual(route_after_monitoring(state), "finish")

    def test_failed_investigation_routes_to_finish(self):
        state = {"workflow_status": "FAILED"}
        self.assertEqual(route_after_investigation(state), "finish")

    def test_successful_investigation_routes_to_llm_analysis(self):
        state = {"workflow_status": "RUNNING"}
        self.assertEqual(route_after_investigation(state), "llm_analysis")

    def test_failed_risk_assessment_routes_to_finish(self):
        state = {"workflow_status": "FAILED"}
        self.assertEqual(route_after_risk_assessment(state), "finish")

    def test_successful_risk_assessment_routes_to_decision(self):
        state = {"workflow_status": "RUNNING"}
        self.assertEqual(route_after_risk_assessment(state), "decision")


if __name__ == "__main__":
    unittest.main()
