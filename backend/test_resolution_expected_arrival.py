import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.engines.resolution_verification import verify_expected_arrival


class ExpectedArrivalVerificationTests(unittest.TestCase):
    def shipment(self, **overrides):
        values = {
            "expected_arrival": datetime.now() - timedelta(days=2),
            "actual_arrival": None,
            "status": "IN_TRANSIT",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_actual_arrival_is_verified(self):
        result = verify_expected_arrival(
            self.shipment(actual_arrival=datetime.now(), status="ON_HOLD")
        )
        self.assertEqual(result["status"], "VERIFIED")

    def test_revised_future_eta_is_verified(self):
        result = verify_expected_arrival(
            self.shipment(expected_arrival=datetime.now() + timedelta(days=1))
        )
        self.assertEqual(result["status"], "VERIFIED")

    def test_delivered_and_cancelled_are_terminal_resolution_evidence(self):
        for status in ("DELIVERED", "CANCELLED"):
            with self.subTest(status=status):
                result = verify_expected_arrival(self.shipment(status=status))
                self.assertEqual(result["status"], "VERIFIED")

    def test_on_hold_with_past_eta_is_not_verified(self):
        result = verify_expected_arrival(
            self.shipment(status="ON_HOLD")
        )
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_in_transit_with_past_eta_is_not_verified(self):
        result = verify_expected_arrival(
            self.shipment(status="IN_TRANSIT")
        )
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_missing_expected_arrival_is_inconclusive(self):
        result = verify_expected_arrival(
            self.shipment(expected_arrival=None)
        )
        self.assertEqual(result["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
