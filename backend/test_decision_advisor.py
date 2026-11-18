import pytest

from app.engines.decision_advisor import parse_decision_advisory


def valid_response():
    return {
        "recommendation": "REVIEW_REQUIRED",
        "confidence": "MEDIUM",
        "rationale": "The available evidence should be checked by a manager.",
        "missing_information": ["Confirm the latest carrier update."]
    }


def test_parse_valid_decision_advisory():
    import json

    result = parse_decision_advisory(json.dumps(valid_response()))

    assert result["recommendation"] == "REVIEW_REQUIRED"
    assert result["confidence"] == "MEDIUM"
    assert result["missing_information"] == [
        "Confirm the latest carrier update."
    ]


def test_parse_json_code_fence():
    import json

    fence = chr(96) * 3
    response = fence + "json\n" + json.dumps(valid_response()) + "\n" + fence

    result = parse_decision_advisory(response)

    assert result["recommendation"] == "REVIEW_REQUIRED"


def test_reject_unsupported_recommendation():
    import json

    payload = valid_response()
    payload["recommendation"] = "APPROVE_AND_EXECUTE"

    with pytest.raises(ValueError, match="recommendation is not allowed"):
        parse_decision_advisory(json.dumps(payload))


def test_reject_extra_output_keys():
    import json

    payload = valid_response()
    payload["action_type"] = "UPDATE_SHIPMENT_STATUS"

    with pytest.raises(ValueError, match="exactly"):
        parse_decision_advisory(json.dumps(payload))


def test_reject_invalid_missing_information():
    import json

    payload = valid_response()
    payload["missing_information"] = "No information"

    with pytest.raises(ValueError, match="must be a list"):
        parse_decision_advisory(json.dumps(payload))


def test_reject_empty_rationale():
    import json

    payload = valid_response()
    payload["rationale"] = " "

    with pytest.raises(ValueError, match="rationale is required"):
        parse_decision_advisory(json.dumps(payload))


def test_reject_non_json_response():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_decision_advisory("This plan looks fine.")
