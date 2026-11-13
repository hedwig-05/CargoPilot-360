
from decimal import Decimal
from types import SimpleNamespace

from app.engines.risk_assessment import calculate_risk_score


# Simulate the active risk configuration.
rules = [
    SimpleNamespace(
        factor_code="DOCUMENT_MISMATCH",
        weight=Decimal("35.00")
    ),
    SimpleNamespace(
        factor_code="ARRIVAL_DELAY",
        weight=Decimal("25.00")
    )
]


# Test 1: One HIGH issue with three duplicate representations.
evidence = {
    "DOCUMENT_MISMATCH": [
        {
            "detail": "Container mismatch in invoice and BOL.",
            "severity": "HIGH",
            "issue_key": "field:container_no",
            "exception_id": 4
        },
        {
            "detail": "container_no: MISMATCH",
            "severity": "MEDIUM",
            "issue_key": "field:container_no",
            "validation_id": 3
        },
        {
            "detail": "container_no: MISMATCH",
            "severity": "MEDIUM",
            "issue_key": "field:container_no",
            "validation_id": 4
        },
        {
            "detail": "container_no: MISMATCH",
            "severity": "MEDIUM",
            "issue_key": "field:container_no",
            "validation_id": 12
        }
    ],
    "ARRIVAL_DELAY": []
}


score, factors = calculate_risk_score(rules, evidence)

print("TEST 1: Duplicate evidence")
print("Total score:", score)

for factor in factors:
    print(
        factor["factor_code"],
        "Weight:", factor["weight"],
        "Points:", factor["points_awarded"]
    )

print("\nExpected DOCUMENT_MISMATCH: 35.00")
print("Expected ARRIVAL_DELAY: 0.00")
print("Expected total: 35.00")


# Test 2: One MEDIUM issue.
medium_evidence = {
    "DOCUMENT_MISMATCH": [
        {
            "detail": "One medium document issue.",
            "severity": "MEDIUM",
            "issue_key": "field:shipper"
        }
    ],
    "ARRIVAL_DELAY": []
}

score, factors = calculate_risk_score(rules, medium_evidence)

print("\nTEST 2: Medium severity")
print("Expected DOCUMENT_MISMATCH: 17.50")
print("Actual:", factors[0]["points_awarded"])


# Test 3: Multiple independent issues must not exceed the weight.
multiple_evidence = {
    "DOCUMENT_MISMATCH": [
        {
            "detail": "Issue one.",
            "severity": "HIGH",
            "issue_key": "field:container_no"
        },
        {
            "detail": "Issue two.",
            "severity": "HIGH",
            "issue_key": "field:shipper"
        }
    ],
    "ARRIVAL_DELAY": []
}

score, factors = calculate_risk_score(rules, multiple_evidence)

print("\nTEST 3: Maximum factor weight")
print("Expected DOCUMENT_MISMATCH: 35.00")
print("Actual:", factors[0]["points_awarded"])
