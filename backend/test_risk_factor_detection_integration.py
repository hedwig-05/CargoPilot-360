import unittest

from app.database.connection import DB_NAME, SessionLocal
from app.engines.risk_assessment import detect_risk_factors
from app.models import Shipment, Exception as ShipmentException


@unittest.skipUnless(
    DB_NAME.lower().endswith("_test"),
    "Safety: integration tests may only run against a database ending in '_test'.",
)
class RiskFactorDetectionIntegrationTests(unittest.TestCase):
    """Verify exception-to-risk-factor mapping against the test database.

    Synthetic rows are flushed inside the test transaction and rolled back
    in tearDown, so they are not retained in the database.
    """

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_rolled_cargo_exception_is_detected_as_rolled_cargo(self):
        shipment = self._shipment_without_test_exception_types()
        if shipment is None:
            self.skipTest(
                "No shipment is available without active test exception types."
            )

        synthetic = ShipmentException(
            shipment_id=shipment.shipment_id,
            exception_type="ROLLED_CARGO",
            description="TEST ONLY: cargo was rolled from the intended sailing.",
            severity="HIGH",
            status="OPEN",
            detected_by="UNIT_TEST",
        )
        self.db.add(synthetic)
        self.db.flush()

        evidence = detect_risk_factors(self.db, shipment.shipment_id)

        self.assertEqual(len(evidence["ROLLED_CARGO"]), 1)
        self.assertEqual(
            evidence["ROLLED_CARGO"][0]["exception_id"],
            synthetic.exception_id,
        )
        self.assertEqual(evidence["ROLLED_CARGO"][0]["severity"], "HIGH")

    def test_stakeholder_response_delay_is_detected_as_stakeholder_delay(self):
        shipment = self._shipment_without_test_exception_types()
        if shipment is None:
            self.skipTest(
                "No shipment is available without active test exception types."
            )

        synthetic = ShipmentException(
            shipment_id=shipment.shipment_id,
            exception_type="STAKEHOLDER_RESPONSE_DELAY",
            description="TEST ONLY: stakeholder response deadline was missed.",
            severity="HIGH",
            status="OPEN",
            detected_by="UNIT_TEST",
        )
        self.db.add(synthetic)
        self.db.flush()

        evidence = detect_risk_factors(self.db, shipment.shipment_id)

        self.assertEqual(len(evidence["STAKEHOLDER_DELAY"]), 1)
        self.assertEqual(
            evidence["STAKEHOLDER_DELAY"][0]["exception_id"],
            synthetic.exception_id,
        )
        self.assertEqual(evidence["STAKEHOLDER_DELAY"][0]["severity"], "HIGH")

    def _shipment_without_test_exception_types(self):
        test_types = [
            "ROLLED_CARGO",
            "STAKEHOLDER_RESPONSE_DELAY",
        ]

        for shipment in self.db.query(Shipment).order_by(Shipment.shipment_id):
            existing = (
                self.db.query(ShipmentException.exception_id)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type.in_(test_types),
                    ShipmentException.status.in_([
                        "OPEN",
                        "INVESTIGATING",
                        "AWAITING_APPROVAL",
                        "IN_PROGRESS",
                        "AWAITING_RESPONSE",
                        "PENDING_3RD_PARTY",
                    ]),
                )
                .first()
            )

            if existing is None:
                return shipment

        return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
