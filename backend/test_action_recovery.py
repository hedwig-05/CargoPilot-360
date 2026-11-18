import unittest

from app.engines.action_recovery import (
    MAX_AUTOMATIC_ATTEMPTS,
    analyze_action_failure,
)


class TestActionRecovery(unittest.TestCase):

    def test_transient_failure_is_retry_candidate_before_limit(self):
        result = analyze_action_failure(
            TimeoutError("temporary timeout"),
            attempt_no=1,
            side_effect_state="NOT_COMMITTED",
        )
        self.assertEqual(result["recovery_decision"], "RETRY_CANDIDATE")
        self.assertTrue(result["retry_allowed"])

    def test_transient_failure_escalates_after_attempt_limit(self):
        result = analyze_action_failure(
            ConnectionError("service unavailable"),
            attempt_no=MAX_AUTOMATIC_ATTEMPTS,
            side_effect_state="NOT_COMMITTED",
        )
        self.assertEqual(result["recovery_decision"], "MANAGER_REVIEW")
        self.assertFalse(result["retry_allowed"])

    def test_invalid_payload_requires_replanning(self):
        result = analyze_action_failure(
            ValueError("invalid status"),
            attempt_no=1,
            side_effect_state="NOT_COMMITTED",
        )
        self.assertEqual(result["recovery_decision"], "REPLAN_REQUIRED")
        self.assertFalse(result["retry_allowed"])

    def test_uncertain_side_effect_never_retries(self):
        result = analyze_action_failure(
            TimeoutError("response lost"),
            attempt_no=1,
            side_effect_state="UNKNOWN",
        )
        self.assertEqual(result["recovery_decision"], "MANUAL_REVIEW")
        self.assertFalse(result["retry_allowed"])

    def test_unclassified_error_requires_manual_review(self):
        result = analyze_action_failure(
            RuntimeError("unexpected failure"),
            attempt_no=1,
            side_effect_state="NOT_COMMITTED",
        )
        self.assertEqual(result["recovery_decision"], "MANUAL_REVIEW")
        self.assertFalse(result["retry_allowed"])


if __name__ == "__main__":
    unittest.main()
