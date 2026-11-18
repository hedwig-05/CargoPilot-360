import unittest
from types import SimpleNamespace

from app.engines.action_recovery import (
    MAX_AUTOMATIC_ATTEMPTS,
    analyze_action_failure,
    request_manager_authorized_retry,
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

    def test_officer_cannot_request_recovery(self):
        officer = SimpleNamespace(
            is_active=True,
            role="OFFICER",
            user_id=12,
            name="Demo Officer",
        )
        with self.assertRaises(PermissionError):
            request_manager_authorized_retry(
                db=None,
                action_id=1,
                manager=officer,
            )

    def test_inactive_manager_cannot_request_recovery(self):
        manager = SimpleNamespace(
            is_active=False,
            role="MANAGER",
            user_id=13,
            name="Inactive Manager",
        )
        with self.assertRaises(PermissionError):
            request_manager_authorized_retry(
                db=None,
                action_id=1,
                manager=manager,
            )


if __name__ == "__main__":
    unittest.main()
