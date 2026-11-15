import unittest
from types import SimpleNamespace

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
        self.query_count = 0

    def query(self, model):
        self.query_count += 1
        return FakeQuery(self.event)


class MilestoneConfirmationAuthorizationTests(unittest.TestCase):
    """Exercise the real confirmation route's ADMIN/MANAGER role dependency.

    The event is already completed so authorised users reach the endpoint's
    business logic and receive its expected 409 response without changing data.
    Officers must be rejected before the database is queried.
    """

    def setUp(self):
        self.event = SimpleNamespace(
            event_id=11,
            shipment_id=4,
            event_type="DOCUMENTATION_COMPLETE",
            event_status="COMPLETED",
        )
        self.db = FakeDB(self.event)
        self.user = SimpleNamespace(
            user_id=1,
            name="Test User",
            role="OFFICER",
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
                "evidence_note": "Test confirmation authorization check.",
            },
        )

    def test_officer_is_forbidden_before_event_is_loaded(self):
        self.user.role = "OFFICER"

        response = self.confirm()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.query_count, 0)

    def test_manager_passes_role_check(self):
        self.user.role = "MANAGER"

        response = self.confirm()

        # The completed-event conflict proves the request passed authorization
        # and reached the route's business logic.
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "This milestone is already completed.")
        self.assertEqual(self.db.query_count, 1)

    def test_admin_passes_role_check(self):
        self.user.role = "ADMIN"

        response = self.confirm()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "This milestone is already completed.")
        self.assertEqual(self.db.query_count, 1)

    def test_unauthenticated_request_is_rejected(self):
        self.client.app.dependency_overrides.pop(get_current_user)

        response = self.confirm()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.query_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
