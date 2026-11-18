"""Deterministic failure classification for action-execution recovery.

This module does not execute retries or alter approved actions. It produces a
bounded, auditable recovery recommendation for the supervisor/manager.
"""

MAX_AUTOMATIC_ATTEMPTS = 2


def analyze_action_failure(
    error: Exception,
    attempt_no: int,
    side_effect_state: str = "UNKNOWN",
) -> dict:
    """Classify a failed attempt without allowing an LLM to override safety."""

    message = str(error).strip() or error.__class__.__name__
    error_type = error.__class__.__name__

    if side_effect_state not in {"NOT_COMMITTED", "COMMITTED", "UNKNOWN"}:
        side_effect_state = "UNKNOWN"

    if side_effect_state != "NOT_COMMITTED":
        return {
            "failure_category": "OUTCOME_UNCERTAIN",
            "recovery_decision": "MANUAL_REVIEW",
            "retry_allowed": False,
            "attempt_no": attempt_no,
            "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
            "side_effect_state": side_effect_state,
            "error_type": error_type,
            "error_message": message,
            "reason": (
                "The operation may already have produced an external effect. "
                "Automatic retry could duplicate that effect."
            ),
        }

    if isinstance(error, (TimeoutError, ConnectionError)):
        if attempt_no < MAX_AUTOMATIC_ATTEMPTS:
            return {
                "failure_category": "TRANSIENT",
                "recovery_decision": "RETRY_CANDIDATE",
                "retry_allowed": True,
                "attempt_no": attempt_no,
                "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
                "side_effect_state": side_effect_state,
                "error_type": error_type,
                "error_message": message,
                "reason": "A transient failure occurred before any side effect was committed.",
            }

        return {
            "failure_category": "RETRY_EXHAUSTED",
            "recovery_decision": "MANAGER_REVIEW",
            "retry_allowed": False,
            "attempt_no": attempt_no,
            "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
            "side_effect_state": side_effect_state,
            "error_type": error_type,
            "error_message": message,
            "reason": "The bounded automatic attempt limit has been reached.",
        }

    if isinstance(error, (ValueError, TypeError)):
        category = "INVALID_ACTION_OR_PAYLOAD"
        decision = "REPLAN_REQUIRED"
        reason = "The action or its payload is invalid and should not be repeated unchanged."
    elif isinstance(error, PermissionError):
        category = "PERMISSION"
        decision = "MANAGER_REVIEW"
        reason = "The operation was not authorised; a manager must review permissions."
    else:
        category = "UNCLASSIFIED"
        decision = "MANUAL_REVIEW"
        reason = "The failure cannot be safely classified for automatic retry."

    return {
        "failure_category": category,
        "recovery_decision": decision,
        "retry_allowed": False,
        "attempt_no": attempt_no,
        "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
        "side_effect_state": side_effect_state,
        "error_type": error_type,
        "error_message": message,
        "reason": reason,
    }
