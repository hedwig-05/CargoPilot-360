import unittest
from copy import deepcopy
from types import SimpleNamespace

from app.engines.exception_lifecycle import (
    _merge_source_evidence,
    OVERDUE_MILESTONE,
)


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def make_exception(status="OPEN", severity="HIGH", sources=None):
    return SimpleNamespace(
        exception_id=10,
        shipment_id=20,
        status=status,
        severity=severity,
        sources=deepcopy(sources),
        eligible_for_verification=False,
        severity_recalculation_pending=False,
    )


class StructuredExceptionSourceTests(unittest.TestCase):
    def test_source_update_preserves_other_sources_and_deep_copies(self):
        db = FakeDB()
        other = {"evidence": {"note": "keep"}, "severity": "LOW", "active": True}
        exception = make_exception(sources={"OTHER_SOURCE": other})
        evidence = {"event_ids": [4], "details": {"event_type": "VESSEL_ARRIVED"}}

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, evidence, "HIGH", True
        )
        evidence["details"]["event_type"] = "MUTATED_AFTER_CALL"

        self.assertEqual(
            exception.sources["OTHER_SOURCE"]["evidence"]["note"], "keep"
        )
        self.assertEqual(
            exception.sources[OVERDUE_MILESTONE]["evidence"]["details"]["event_type"],
            "VESSEL_ARRIVED",
        )
        self.assertIsNot(exception.sources["OTHER_SOURCE"], other)

    def test_all_sources_inactive_sets_readiness_without_resolving(self):
        db = FakeDB()
        exception = make_exception(sources={
            OVERDUE_MILESTONE: {
                "evidence": {"event_ids": [4]}, "severity": "HIGH",
                "active": True, "cleared_at": None,
            }
        })

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE,
            {"event_ids": [4], "status": "completed"}, "HIGH", False
        )

        self.assertTrue(exception.eligible_for_verification)
        self.assertEqual(exception.status, "OPEN")
        self.assertEqual(exception.severity, "HIGH")
        self.assertIsNotNone(exception.sources[OVERDUE_MILESTONE]["cleared_at"])

    def test_reactivated_source_flips_readiness_back_to_false(self):
        db = FakeDB()
        exception = make_exception(sources={
            OVERDUE_MILESTONE: {
                "evidence": {"status": "completed"}, "severity": "HIGH",
                "active": False, "cleared_at": "2026-11-15T10:00:00",
            }
        })
        exception.eligible_for_verification = True

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE,
            {"event_ids": [4], "status": "overdue"}, "HIGH", True
        )

        self.assertFalse(exception.eligible_for_verification)
        self.assertIsNone(exception.sources[OVERDUE_MILESTONE]["cleared_at"])

    def test_protected_exception_upgrades_immediately_and_defers_downgrade(self):
        db = FakeDB()
        exception = make_exception(status="INVESTIGATING", severity="MEDIUM")

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, {"reason": "urgent"}, "CRITICAL", True
        )
        self.assertEqual(exception.severity, "CRITICAL")
        self.assertFalse(exception.severity_recalculation_pending)

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, {"reason": "less urgent"}, "LOW", True
        )
        self.assertEqual(exception.severity, "CRITICAL")
        self.assertTrue(exception.severity_recalculation_pending)

    def test_identical_source_update_does_not_add_audit_record(self):
        db = FakeDB()
        exception = make_exception(sources={
            OVERDUE_MILESTONE: {
                "evidence": {"event_ids": [4]}, "severity": "HIGH",
                "active": True, "created_at": "2026-11-15T10:00:00",
                "updated_at": "2026-11-15T10:00:00", "cleared_at": None,
            }
        })

        # The timestamp is metadata, not evidence; the audit is based on
        # evidence/severity/active-state changes.
        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, {"event_ids": [4]}, "HIGH", True
        )
        first_count = len(db.added)
        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, {"event_ids": [4]}, "HIGH", True
        )
        self.assertEqual(len(db.added), first_count)

    def test_repeated_clear_preserves_original_cleared_timestamp(self):
        db = FakeDB()
        exception = make_exception(sources={
            OVERDUE_MILESTONE: {
                "evidence": {"status": "done"}, "severity": "HIGH",
                "active": False, "created_at": "2026-11-15T10:00:00",
                "updated_at": "2026-11-15T10:00:00",
                "cleared_at": "2026-11-15T10:00:00",
            }
        })
        exception.eligible_for_verification = True

        _merge_source_evidence(
            db, exception, OVERDUE_MILESTONE, {"status": "done"}, "HIGH", False
        )
        self.assertEqual(
            exception.sources[OVERDUE_MILESTONE]["cleared_at"],
            "2026-11-15T10:00:00",
        )



# Database-backed transition regression. These tests are deliberately skipped
# unless the process is configured to use the disposable *_test database.
from app.database.connection import DB_NAME, SessionLocal
from app.models import Shipment, Exception as ShipmentException
from app.engines.exception_lifecycle import (
    create_or_update_exception,
    transition_exception_status,
)


@unittest.skipUnless(
    DB_NAME.lower().endswith("_test"),
    "Safety: source lifecycle integration tests require a *_test database.",
)
class DeferredSeverityDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.shipment = None
        for shipment in self.db.query(Shipment).order_by(Shipment.shipment_id):
            active = (
                self.db.query(ShipmentException.exception_id)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type == "STAKEHOLDER_RESPONSE_DELAY",
                    ShipmentException.status.in_([
                        "OPEN", "INVESTIGATING", "AWAITING_APPROVAL",
                        "IN_PROGRESS", "AWAITING_RESPONSE", "PENDING_3RD_PARTY",
                    ]),
                )
                .first()
            )
            if active is None:
                self.shipment = shipment
                break
        if self.shipment is None:
            self.db.close()
            self.skipTest("No shipment available for rolled-back source test.")

    def tearDown(self):
        if self.db.is_active:
            self.db.rollback()
        self.db.close()

    def test_deferred_downgrade_is_applied_once_when_reopened(self):
        created = create_or_update_exception(
            db=self.db,
            shipment_id=self.shipment.shipment_id,
            exception_type="STAKEHOLDER_RESPONSE_DELAY",
            description="Legacy-compatible test description.",
            severity="HIGH",
            detected_by="UNIT_TEST",
            source_key=OVERDUE_MILESTONE,
            source_evidence={"event_ids": [999999]},
            source_active=True,
            commit=False,
        )
        exception_id = created["exception_id"]

        transition_exception_status(
            self.db, exception_id, "INVESTIGATING", commit=False
        )
        create_or_update_exception(
            db=self.db,
            shipment_id=self.shipment.shipment_id,
            exception_type="STAKEHOLDER_RESPONSE_DELAY",
            description="Not used for structured update.",
            severity="LOW",
            detected_by="UNIT_TEST",
            source_key=OVERDUE_MILESTONE,
            source_evidence={"event_ids": [999999], "status": "cleared"},
            source_active=True,
            commit=False,
        )

        exception = self.db.query(ShipmentException).get(exception_id)
        self.assertEqual(exception.severity, "HIGH")
        self.assertTrue(exception.severity_recalculation_pending)

        transition_exception_status(
            self.db, exception_id, "OPEN", commit=False
        )
        self.assertEqual(exception.severity, "LOW")
        self.assertFalse(exception.severity_recalculation_pending)



class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result


class FakeNestedTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class DuplicateInsertDB:
    """Simulate the unique-open_key loser after another transaction wins."""
    def __init__(self, winner):
        self.winner = winner
        self.flush_calls = 0
        self.added = []

    def query(self, model):
        return FakeQuery(self.winner)

    def begin_nested(self):
        return FakeNestedTransaction()

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flush_calls += 1
        if self.flush_calls == 1:
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError("INSERT exceptions", {}, Exception("duplicate open_key"))


class ConcurrentCreateRecoveryTests(unittest.TestCase):
    def test_losing_writer_merges_source_into_winning_exception(self):
        from app.engines.exception_lifecycle import create_or_update_exception

        winner = make_exception(
            status="OPEN",
            severity="MEDIUM",
            sources={
                "WINNER_SOURCE": {
                    "evidence": {"winner": True},
                    "severity": "MEDIUM",
                    "active": True,
                }
            },
        )
        winner.exception_type = "SHIPMENT_DELAY"
        winner.description = "Winner exception"
        winner.event_id = None
        winner.document_id = None
        db = DuplicateInsertDB(winner)

        result = create_or_update_exception(
            db=db,
            shipment_id=winner.shipment_id,
            exception_type="SHIPMENT_DELAY",
            description="Losing writer description",
            severity="HIGH",
            detected_by="UNIT_TEST",
            commit=False,
            source_key=OVERDUE_MILESTONE,
            source_evidence={"events": [{"event_id": 444, "event_type": "VESSEL_ARRIVED"}]},
            source_active=True,
        )

        self.assertEqual(result["operation"], "UPDATED")
        self.assertEqual(result["exception_id"], winner.exception_id)
        self.assertTrue(winner.sources["WINNER_SOURCE"]["evidence"]["winner"])
        self.assertEqual(
            winner.sources[OVERDUE_MILESTONE]["evidence"]["events"][0]["event_id"],
            444,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
