import unittest
from datetime import datetime

from app.database.connection import DB_NAME, SessionLocal
from app.engines.risk_assessment import detect_risk_factors
from app.models import (
    Shipment,
    ShipmentEvent,
    Exception as ShipmentException,
)


@unittest.skipUnless(
    DB_NAME.lower().endswith("_test"),
    "Safety: integration tests may only run against a database ending in '_test'.",
)
class ExistingExceptionRiskMappingTests(unittest.TestCase):
    """Exercise the remaining exception-to-risk-factor mappings.

    Every synthetic row is created inside the test transaction. tearDown
    rolls the transaction back, leaving the test database unchanged.
    """

    ACTIVE_STATUSES = [
        "OPEN",
        "INVESTIGATING",
        "AWAITING_APPROVAL",
        "IN_PROGRESS",
        "AWAITING_RESPONSE",
        "PENDING_3RD_PARTY",
    ]

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_damage_shortage_maps_to_damage_shortage(self):
        self._assert_mapping("DAMAGE_SHORTAGE", "DAMAGE_SHORTAGE")

    def test_document_mismatch_maps_to_document_mismatch(self):
        self._assert_mapping(
            "DOCUMENT_MISMATCH",
            "DOCUMENT_MISMATCH",
            description="TEST ONLY: Affected fields: shipper.",
        )

    def test_missing_document_maps_to_missing_document(self):
        self._assert_mapping("MISSING_DOCUMENT", "MISSING_DOCUMENT")

    def test_customs_hold_maps_to_customs_issue(self):
        self._assert_mapping("CUSTOMS_HOLD", "CUSTOMS_ISSUE")

    def test_missing_milestone_maps_to_missing_milestone(self):
        self._assert_mapping("MISSING_MILESTONE", "MISSING_MILESTONE")

    def test_container_not_discharged_maps_to_missing_milestone(self):
        self._assert_mapping(
            "CONTAINER_NOT_DISCHARGED",
            "MISSING_MILESTONE",
        )

    def test_customs_clearance_shipment_delay_maps_to_customs_issue(self):
        self._assert_mapping(
            "SHIPMENT_DELAY",
            "CUSTOMS_ISSUE",
            event_type="CUSTOMS_CLEARED",
        )

    def test_vessel_arrival_shipment_delay_maps_to_arrival_delay(self):
        self._assert_mapping(
            "SHIPMENT_DELAY",
            "ARRIVAL_DELAY",
            event_type="VESSEL_ARRIVED",
        )

    def _assert_mapping(
        self,
        exception_type,
        expected_factor,
        description=None,
        event_type=None,
    ):
        shipment = self._find_eligible_shipment(exception_type)
        if shipment is None:
            self.skipTest(
                f"No shipment is available for a temporary {exception_type} row."
            )

        event = None
        if event_type:
            event = ShipmentEvent(
                shipment_id=shipment.shipment_id,
                event_type=event_type,
                event_description="TEST ONLY: synthetic mapping event.",
                expected_time=datetime.now(),
                event_status="PENDING",
                source="UNIT_TEST",
            )
            self.db.add(event)
            self.db.flush()

        synthetic = ShipmentException(
            shipment_id=shipment.shipment_id,
            exception_type=exception_type,
            description=description or f"TEST ONLY: {exception_type} mapping.",
            severity="HIGH",
            status="OPEN",
            event_id=event.event_id if event else None,
            detected_by="UNIT_TEST",
        )
        self.db.add(synthetic)
        self.db.flush()

        evidence = detect_risk_factors(self.db, shipment.shipment_id)
        matching = [
            item for item in evidence[expected_factor]
            if item.get("exception_id") == synthetic.exception_id
        ]

        self.assertEqual(
            len(matching),
            1,
            msg=(
                f"{exception_type} should produce exactly one "
                f"{expected_factor} evidence item."
            ),
        )
        self.assertEqual(matching[0]["severity"], "HIGH")

    def _find_eligible_shipment(self, exception_type):
        for shipment in self.db.query(Shipment).order_by(Shipment.shipment_id):
            existing = (
                self.db.query(ShipmentException.exception_id)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type == exception_type,
                    ShipmentException.status.in_(self.ACTIVE_STATUSES),
                )
                .first()
            )
            if existing is None:
                return shipment
        return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
