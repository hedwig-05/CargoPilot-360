import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import Shipment, Exception as ShipmentException
from app.engines.exception_detection import detect_expected_arrival_delays
from app.engines.exception_lifecycle import EXPECTED_ARRIVAL


class FakeQuery:
    def __init__(self, rows=None, first_row=None):
        self.rows = rows or []
        self.first_row = first_row

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.first_row


class FakeDB:
    def __init__(self, shipments, existing_exception=None):
        self.shipments = shipments
        self.existing_exception = existing_exception
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    def query(self, model):
        if model is Shipment:
            return FakeQuery(rows=self.shipments)
        if model is ShipmentException:
            return FakeQuery(first_row=self.existing_exception)
        raise AssertionError(f"Unexpected model queried: {model}")

    def commit(self):
        self.commits += 1

    def flush(self):
        self.flushes += 1

    def rollback(self):
        self.rollbacks += 1


def make_shipment(**overrides):
    values = {
        "shipment_id": 7,
        "shipment_ref": "CP-TEST-007",
        "expected_arrival": datetime.now() - timedelta(hours=2),
        "actual_arrival": None,
        "status": "IN_TRANSIT",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ExpectedArrivalDetectionTests(unittest.TestCase):
    @patch("app.engines.exception_detection.create_or_update_exception")
    def test_overdue_eta_creates_structured_expected_arrival_source(self, create):
        create.return_value = {"operation": "CREATED"}
        db = FakeDB([make_shipment(status="ON_HOLD")])

        result = detect_expected_arrival_delays(db, commit=False)

        self.assertEqual(result["exceptions_created"], 1)
        self.assertEqual(result["shipments_checked"], 1)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["source_key"], EXPECTED_ARRIVAL)
        self.assertTrue(kwargs["source_active"])
        self.assertEqual(kwargs["source_evidence"]["shipment_status"], "ON_HOLD")
        self.assertTrue(kwargs["source_evidence"]["on_hold"])
        self.assertEqual(kwargs["severity"], "HIGH")
        self.assertEqual(db.flushes, 1)

    @patch("app.engines.exception_detection.create_or_update_exception")
    def test_future_eta_does_not_create_an_exception_without_active_source(self, create):
        db = FakeDB([
            make_shipment(expected_arrival=datetime.now() + timedelta(days=1))
        ])

        result = detect_expected_arrival_delays(db, commit=False)

        create.assert_not_called()
        self.assertEqual(result["exceptions_created"], 0)
        self.assertEqual(result["sources_cleared"], 0)
        self.assertEqual(result["unchanged"], 1)

    @patch("app.engines.exception_detection.create_or_update_exception")
    def test_revised_future_eta_clears_existing_active_source(self, create):
        create.return_value = {"operation": "UPDATED"}
        existing = SimpleNamespace(
            description="Active delay",
            sources={
                EXPECTED_ARRIVAL: {
                    "active": True,
                    "severity": "HIGH",
                    "evidence": {"expected_arrival": "old"},
                }
            },
        )
        shipment = make_shipment(
            expected_arrival=datetime.now() + timedelta(days=1)
        )
        db = FakeDB([shipment], existing_exception=existing)

        result = detect_expected_arrival_delays(db, commit=False)

        self.assertEqual(result["sources_cleared"], 1)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["source_key"], EXPECTED_ARRIVAL)
        self.assertFalse(kwargs["source_active"])
        self.assertEqual(kwargs["source_evidence"]["shipment_status"], "IN_TRANSIT")

    @patch("app.engines.exception_detection.create_or_update_exception")
    def test_actual_arrival_clears_existing_active_source(self, create):
        create.return_value = {"operation": "UPDATED"}
        existing = SimpleNamespace(
            description="Active delay",
            sources={
                EXPECTED_ARRIVAL: {
                    "active": True,
                    "severity": "HIGH",
                    "evidence": {},
                }
            },
        )
        shipment = make_shipment(actual_arrival=datetime.now())
        db = FakeDB([shipment], existing_exception=existing)

        result = detect_expected_arrival_delays(db, commit=False)

        self.assertEqual(result["sources_cleared"], 1)
        self.assertFalse(create.call_args.kwargs["source_active"])

    @patch("app.engines.exception_detection.create_or_update_exception")
    def test_terminal_shipment_clears_existing_active_source(self, create):
        create.return_value = {"operation": "UPDATED"}
        existing = SimpleNamespace(
            description="Active delay",
            sources={
                EXPECTED_ARRIVAL: {
                    "active": True,
                    "severity": "HIGH",
                    "evidence": {},
                }
            },
        )
        shipment = make_shipment(status="DELIVERED")
        db = FakeDB([shipment], existing_exception=existing)

        result = detect_expected_arrival_delays(db, commit=False)

        self.assertEqual(result["sources_cleared"], 1)
        self.assertEqual(
            create.call_args.kwargs["source_evidence"]["shipment_status"],
            "DELIVERED",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
