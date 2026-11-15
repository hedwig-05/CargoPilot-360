"""Fast, database-free regression tests for core CargoPilot components.

Run from the backend directory with:
    python -m unittest test_component_regression -v
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.engines.risk_assessment import (
    calculate_risk_score,
    determine_risk_level,
    get_overdue_event_factor,
)
from app.llm.router import LLMRouter


class FakeProvider:
    def __init__(self, model="fake-model", response="ok", error=None):
        self.model = model
        self.response = response
        self.error = error
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


class RiskScoringRegressionTests(unittest.TestCase):
    def setUp(self):
        weights = {
            "DAMAGE_SHORTAGE": "20",
            "DOCUMENT_MISMATCH": "20",
            "CUSTOMS_ISSUE": "15",
            "ROLLED_CARGO": "15",
            "ARRIVAL_DELAY": "10",
            "MISSING_MILESTONE": "10",
            "MISSING_DOCUMENT": "5",
            "STAKEHOLDER_DELAY": "5",
        }
        self.rules = [
            SimpleNamespace(factor_code=code, weight=Decimal(weight))
            for code, weight in weights.items()
        ]

    def test_eight_high_factors_cap_at_one_hundred(self):
        evidence = {
            rule.factor_code: [{
                "issue_key": f"issue:{rule.factor_code}",
                "severity": "HIGH",
            }]
            for rule in self.rules
        }
        score, factors = calculate_risk_score(self.rules, evidence)
        self.assertEqual(score, Decimal("100.00"))
        self.assertEqual(len(factors), 8)

    def test_duplicate_evidence_uses_strongest_severity_once(self):
        rules = [SimpleNamespace(
            factor_code="DOCUMENT_MISMATCH",
            weight=Decimal("20"),
        )]
        evidence = {"DOCUMENT_MISMATCH": [
            {"issue_key": "container_no", "severity": "MEDIUM"},
            {"issue_key": "container_no", "severity": "HIGH"},
        ]}
        score, factors = calculate_risk_score(rules, evidence)
        self.assertEqual(score, Decimal("20.00"))
        self.assertEqual(len(factors[0]["evidence"]), 1)

    def test_medium_severity_awards_half_factor_weight(self):
        rules = [SimpleNamespace(
            factor_code="DAMAGE_SHORTAGE",
            weight=Decimal("20"),
        )]
        score, _ = calculate_risk_score(rules, {
            "DAMAGE_SHORTAGE": [
                {"issue_key": "damage:1", "severity": "MEDIUM"}
            ]
        })
        self.assertEqual(score, Decimal("10.00"))

    def test_risk_threshold_boundaries(self):
        config = SimpleNamespace(
            low_max_score=Decimal("29"),
            medium_max_score=Decimal("59"),
        )
        self.assertEqual(determine_risk_level(Decimal("29"), config), "LOW")
        self.assertEqual(determine_risk_level(Decimal("29.01"), config), "MEDIUM")
        self.assertEqual(determine_risk_level(Decimal("59"), config), "MEDIUM")
        self.assertEqual(determine_risk_level(Decimal("59.01"), config), "HIGH")

    def test_overdue_event_classification_and_completed_event_exclusion(self):
        now = datetime(2026, 11, 14, 12, 0, 0)
        overdue = now - timedelta(hours=1)
        self.assertEqual(
            get_overdue_event_factor(SimpleNamespace(
                event_status="PENDING",
                expected_time=overdue,
                event_type="CUSTOMS_CLEARED",
            ), now),
            "CUSTOMS_ISSUE",
        )
        self.assertIsNone(get_overdue_event_factor(SimpleNamespace(
            event_status="COMPLETED",
            expected_time=overdue,
            event_type="VESSEL_ARRIVED",
        ), now))


class LLMRouterRegressionTests(unittest.TestCase):
    def test_primary_provider_success_does_not_call_fallback(self):
        primary = FakeProvider(response="primary answer")
        fallback = FakeProvider(response="fallback answer")
        result = LLMRouter(primary, fallback).generate_with_metadata("prompt")
        self.assertEqual(result["content"], "primary answer")
        self.assertFalse(result["fallback_used"])
        self.assertEqual(primary.calls, 1)
        self.assertEqual(fallback.calls, 0)

    def test_fallback_is_used_when_primary_fails(self):
        primary = FakeProvider(error=RuntimeError("primary offline"))
        fallback = FakeProvider(response="fallback answer")
        result = LLMRouter(primary, fallback).generate_with_metadata("prompt")
        self.assertEqual(result["content"], "fallback answer")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(primary.calls, 1)
        self.assertEqual(fallback.calls, 1)

    def test_primary_failure_without_fallback_is_reported(self):
        primary = FakeProvider(error=RuntimeError("primary offline"))
        with self.assertRaisesRegex(RuntimeError, "no usable fallback"):
            LLMRouter(primary).generate_with_metadata("prompt")

    def test_both_provider_failures_are_reported(self):
        primary = FakeProvider(error=RuntimeError("primary offline"))
        fallback = FakeProvider(error=RuntimeError("fallback offline"))
        with self.assertRaisesRegex(RuntimeError, "Both primary and fallback"):
            LLMRouter(primary, fallback).generate_with_metadata("prompt")


if __name__ == "__main__":
    unittest.main()
