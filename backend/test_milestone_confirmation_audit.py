import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.shipment_events import router as shipment_events_router
from app.auth.dependencies import get_current_user
from app.database.connection import get_db


class FakeQuery:
    def __init__(self, record):
        self.record = record

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.record


class FakeDB:
    def __init__(self, event):
        self.event = event
        self.audit_records = []
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0

    def query(self, model):
        return FakeQuery(self.event)

    def add(self, record):
        self.audit_records.append(record)

    def commit(self):
        self.commit_count += 1

    def refresh(self, record):
        self.refresh_count += 1

    def rollback(self):
        self.rollback_count += 1


class MilestoneConfirmationAuditTests(unittest.TestCase):
    """Verify successful confirmation is audited once and cannot be audited twice."""

    def setUp(self):
        self.event = SimpleNamespace(
            event_id=11,
            shipment_id=4,
            event_type="DOCUMENTATION_COMPLETE",
            event_status="INCONSISTENT",
            actual_time=None,
            source="SYSTEM",
        )
        self.db = FakeDB(self.event)
        self.user = SimpleNamespace(
            user_id=2,
            name="Test Manager",
            role="MANAGER",
        )

        app = FastAPI()
        app.include_router(shipment_events_router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def confirm(self):
        return self.client.post(
            "/api/shipments/4/events/11/confirm",
            json={
                "actual_time": "2026-11-12T18:00:00",
                "evidence_note": "Manager reviewed the invoice and bill of lading.",
            },
        )

    @patch(
        "app.api.shipment_events.assess_milestone_reconciliation",
        return_value={"ready_for_confirmation": True},
    )
    def test_offset_aware_actual_time_is_normalized_to_utc(self, assessment):
        response = self.client.post(
            "/api/shipments/4/events/11/confirm",
            json={
                "actual_time": "2026-11-12T21:00:00+05:30",
                "evidence_note": "Manager verified the milestone evidence.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.event.actual_time,
            datetime(2026, 11, 12, 15, 30),
        )
        self.assertEqual(
            self.db.audit_records[0].details["actual_time"],
            "2026-11-12T15:30:00",
        )
        self.assertEqual(self.event.source, "SYSTEM")
        assessment.assert_called_once()

    @patch(
        "app.api.shipment_events.assess_milestone_reconciliation",
        return_value={"ready_for_confirmation": True},
    )
    def test_successful_confirmation_creates_one_audit_and_duplicate_creates_none(self, assessment):
        first_response = self.confirm()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["event_status"], "COMPLETED")
        self.assertEqual(self.event.event_status, "COMPLETED")
        self.assertEqual(self.event.source, "SYSTEM")
        self.assertEqual(len(self.db.audit_records), 1)
        self.assertEqual(self.db.commit_count, 1)

        audit = self.db.audit_records[0]
        self.assertEqual(audit.actor_type, "USER")
        self.assertEqual(audit.actor_user_id, self.user.user_id)
        self.assertEqual(audit.actor_name, self.user.name)
        self.assertEqual(audit.action, "SHIPMENT_MILESTONE_CONFIRMED")
        self.assertEqual(audit.entity_type, "SHIPMENT_EVENT")
        self.assertEqual(audit.entity_id, self.event.event_id)
        self.assertEqual(audit.shipment_id, self.event.shipment_id)
        self.assertEqual(audit.details["previous_status"], "INCONSISTENT")
        self.assertEqual(audit.details["new_status"], "COMPLETED")
        self.assertEqual(
            audit.details["actual_time"],
            "2026-11-12T18:00:00",
        )
        self.assertEqual(
            audit.details["evidence_note"],
            "Manager reviewed the invoice and bill of lading.",
        )

        second_response = self.confirm()

        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(
            second_response.json()["detail"],
            "This milestone is already completed.",
        )
        self.assertEqual(len(self.db.audit_records), 1)
        self.assertEqual(self.db.commit_count, 1)
        self.assertEqual(self.db.rollback_count, 0)
        assessment.assert_called_once()

if __name__ == "__main__":
    unittest.main(verbosity=2)
