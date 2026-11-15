from decimal import Decimal
from types import SimpleNamespace
import unittest

from app.engines.risk_assessment import calculate_risk_score


class RiskFactorCoverageTests(unittest.TestCase):
    """Isolated scoring tests for the eight-factor risk configuration.

    These tests use controlled evidence and do not connect to MySQL.
    They validate scoring, not database evidence detection/mapping.
    """

    def setUp(self):
        self.rules = [
            SimpleNamespace(factor_code="DAMAGE_SHORTAGE", weight=Decimal("20.00")),
            SimpleNamespace(factor_code="DOCUMENT_MISMATCH", weight=Decimal("20.00")),
            SimpleNamespace(factor_code="CUSTOMS_ISSUE", weight=Decimal("15.00")),
            SimpleNamespace(factor_code="ROLLED_CARGO", weight=Decimal("15.00")),
            SimpleNamespace(factor_code="ARRIVAL_DELAY", weight=Decimal("10.00")),
            SimpleNamespace(factor_code="MISSING_MILESTONE", weight=Decimal("10.00")),
            SimpleNamespace(factor_code="MISSING_DOCUMENT", weight=Decimal("5.00")),
            SimpleNamespace(factor_code="STAKEHOLDER_DELAY", weight=Decimal("5.00")),
        ]

    def factor(self, results, code):
        return next(item for item in results if item["factor_code"] == code)

    def test_configuration_contains_all_eight_factors_and_weights_total_100(self):
        codes = {rule.factor_code for rule in self.rules}
        self.assertEqual(len(codes), 8)
        self.assertEqual(
            sum((rule.weight for rule in self.rules), Decimal("0.00")),
            Decimal("100.00"),
        )

    def test_rolled_cargo_high_severity_awards_full_factor_weight(self):
        evidence = {
            "ROLLED_CARGO": [{
                "detail": "Cargo was not loaded on the intended sailing.",
                "severity": "HIGH",
                "issue_key": "exception:rolled-1",
                "exception_id": 101,
            }]
        }

        score, results = calculate_risk_score(self.rules, evidence)

        self.assertEqual(score, Decimal("15.00"))
        self.assertEqual(
            self.factor(results, "ROLLED_CARGO")["points_awarded"],
            Decimal("15.00"),
        )

    def test_stakeholder_delay_high_severity_awards_full_factor_weight(self):
        evidence = {
            "STAKEHOLDER_DELAY": [{
                "detail": "Required carrier response is overdue.",
                "severity": "HIGH",
                "issue_key": "exception:stakeholder-1",
                "exception_id": 102,
            }]
        }

        score, results = calculate_risk_score(self.rules, evidence)

        self.assertEqual(score, Decimal("5.00"))
        self.assertEqual(
            self.factor(results, "STAKEHOLDER_DELAY")["points_awarded"],
            Decimal("5.00"),
        )

    def test_both_factors_are_scored_independently(self):
        evidence = {
            "ROLLED_CARGO": [{
                "detail": "Cargo missed the intended vessel.",
                "severity": "HIGH",
                "issue_key": "exception:rolled-2",
            }],
            "STAKEHOLDER_DELAY": [{
                "detail": "Carrier has not responded.",
                "severity": "HIGH",
                "issue_key": "exception:stakeholder-2",
            }],
        }

        score, results = calculate_risk_score(self.rules, evidence)

        self.assertEqual(score, Decimal("20.00"))
        self.assertEqual(
            self.factor(results, "ROLLED_CARGO")["points_awarded"],
            Decimal("15.00"),
        )
        self.assertEqual(
            self.factor(results, "STAKEHOLDER_DELAY")["points_awarded"],
            Decimal("5.00"),
        )

    def test_duplicate_evidence_for_same_issue_is_not_counted_twice(self):
        evidence = {
            "ROLLED_CARGO": [
                {
                    "detail": "Cargo missed the intended vessel.",
                    "severity": "HIGH",
                    "issue_key": "exception:rolled-3",
                    "exception_id": 103,
                },
                {
                    "detail": "Same rolled-cargo issue from another source.",
                    "severity": "MEDIUM",
                    "issue_key": "exception:rolled-3",
                    "event_id": 203,
                },
            ]
        }

        score, results = calculate_risk_score(self.rules, evidence)
        rolled = self.factor(results, "ROLLED_CARGO")

        self.assertEqual(score, Decimal("15.00"))
        self.assertEqual(rolled["points_awarded"], Decimal("15.00"))
        self.assertEqual(len(rolled["evidence"]), 1)
        self.assertEqual(rolled["evidence"][0]["event_id"], 203)

    def test_medium_stakeholder_delay_awards_half_factor_weight(self):
        evidence = {
            "STAKEHOLDER_DELAY": [{
                "detail": "A response is delayed.",
                "severity": "MEDIUM",
                "issue_key": "exception:stakeholder-3",
            }]
        }

        score, results = calculate_risk_score(self.rules, evidence)

        self.assertEqual(score, Decimal("2.50"))
        self.assertEqual(
            self.factor(results, "STAKEHOLDER_DELAY")["points_awarded"],
            Decimal("2.50"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
