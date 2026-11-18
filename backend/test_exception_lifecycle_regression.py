import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from app.database.connection import DB_NAME, SessionLocal
from app.engines.exception_lifecycle import (
    create_or_update_exception,
    resolve_exception,
    transition_exception_status,
)
from app.models import (
    Shipment,
    Exception as ShipmentException,
    ExceptionStatusHistory,
    AgentWorkflow,
    AgentRun,
    ResolutionVerification,
)


@unittest.skipUnless(
    DB_NAME.lower().endswith("_test"),
    "Safety: exception lifecycle integration tests require a *_test database.",
)
class ExceptionLifecycleRegressionTests(unittest.TestCase):
    """Database-backed lifecycle regressions; all synthetic rows are rolled back."""

    EXCEPTION_TYPE = "STAKEHOLDER_RESPONSE_DELAY"

    def setUp(self):
        self.db = SessionLocal()
        self.shipment = self._find_shipment_without_active_test_exception()
        if self.shipment is None:
            self.db.close()
            self.skipTest(
                "No shipment is available without an active "
                "STAKEHOLDER_RESPONSE_DELAY exception."
            )

    def tearDown(self):
        if self.db.is_active:
            self.db.rollback()
        self.db.close()

    def _find_shipment_without_active_test_exception(self):
        active_statuses = [
            "OPEN",
            "INVESTIGATING",
            "AWAITING_APPROVAL",
            "IN_PROGRESS",
            "AWAITING_RESPONSE",
            "PENDING_3RD_PARTY",
        ]
        for shipment in self.db.query(Shipment).order_by(Shipment.shipment_id):
            existing = (
                self.db.query(ShipmentException.exception_id)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type == self.EXCEPTION_TYPE,
                    ShipmentException.status.in_(active_statuses),
                )
                .first()
            )
            if existing is None:
                return shipment
        return None

    def _create_exception(self):
        result = create_or_update_exception(
            db=self.db,
            shipment_id=self.shipment.shipment_id,
            exception_type=self.EXCEPTION_TYPE,
            description="TEST ONLY: exception lifecycle regression.",
            severity="LOW",
            detected_by="UNIT_TEST",
            commit=False,
        )
        self.assertEqual(result["operation"], "CREATED")
        return result["exception_id"]

    def _get_exception(self, exception_id):
        return (
            self.db.query(ShipmentException)
            .filter(ShipmentException.exception_id == exception_id)
            .one()
        )

    def _create_verification(
        self,
        exception_id,
        verification_status,
        shipment_id=None,
        verified_at=None,
    ):
        exception = self._get_exception(exception_id)
        unique_id = uuid4().hex

        workflow = AgentWorkflow(
            workflow_public_id=f"TEST-WF-{unique_id}",
            thread_id=f"TEST-THREAD-{unique_id}",
            shipment_id=exception.shipment_id,
            exception_id=exception_id,
            trigger_type="MANUAL",
            graph_name="cargopilot_main",
            status="COMPLETED",
            current_node="RESOLUTION_VERIFICATION",
        )
        self.db.add(workflow)
        self.db.flush()

        run = AgentRun(
            run_public_id=f"TEST-RUN-{unique_id}",
            workflow_id=workflow.workflow_id,
            step_no=1,
            agent_type="VERIFICATION",
            node_name="resolution_verification",
            execution_status="COMPLETED",
        )
        self.db.add(run)
        self.db.flush()

        verification = ResolutionVerification(
            exception_id=exception_id,
            shipment_id=(
                shipment_id if shipment_id is not None
                else exception.shipment_id
            ),
            workflow_id=workflow.workflow_id,
            run_id=run.run_id,
            verification_status=verification_status,
            evidence_summary="TEST ONLY: lifecycle verification fixture.",
            validation_results=[],
            verified_at=verified_at or datetime.now(),
        )
        self.db.add(verification)
        self.db.flush()
        return verification

    def test_creation_records_initial_open_history(self):
        exception_id = self._create_exception()

        history = (
            self.db.query(ExceptionStatusHistory)
            .filter(ExceptionStatusHistory.exception_id == exception_id)
            .order_by(ExceptionStatusHistory.log_id)
            .all()
        )

        self.assertEqual(len(history), 1)
        self.assertIsNone(history[0].old_status)
        self.assertEqual(history[0].new_status, "OPEN")

    def test_duplicate_detection_does_not_overwrite_protected_workflow(self):
        exception_id = self._create_exception()
        transition_exception_status(
            self.db, exception_id, "INVESTIGATING", commit=False
        )
        original = self._get_exception(exception_id)
        original_description = original.description

        result = create_or_update_exception(
            db=self.db,
            shipment_id=self.shipment.shipment_id,
            exception_type=self.EXCEPTION_TYPE,
            description="TEST ONLY: attempted overwrite.",
            severity="CRITICAL",
            detected_by="UNIT_TEST",
            commit=False,
        )

        self.assertEqual(result["operation"], "SKIPPED")
        self.assertEqual(result["exception_id"], exception_id)
        self.assertEqual(original.description, original_description)
        self.assertEqual(original.severity, "LOW")

    def test_investigating_transition_records_acknowledgement_time(self):
        exception_id = self._create_exception()

        result = transition_exception_status(
            self.db, exception_id, "INVESTIGATING", commit=False
        )

        self.assertIsNotNone(result["acknowledged_at"])
        self.assertEqual(self._get_exception(exception_id).status, "INVESTIGATING")

    def test_only_pending_third_party_time_is_added_to_sla_pause(self):
        exception_id = self._create_exception()

        transition_exception_status(
            self.db, exception_id, "AWAITING_RESPONSE", commit=False
        )
        transition_exception_status(
            self.db, exception_id, "INVESTIGATING", commit=False
        )
        self.assertEqual(self._get_exception(exception_id).total_paused_minutes, 0)

        transition_exception_status(
            self.db, exception_id, "PENDING_3RD_PARTY", commit=False
        )
        pause_entry = (
            self.db.query(ExceptionStatusHistory)
            .filter(
                ExceptionStatusHistory.exception_id == exception_id,
                ExceptionStatusHistory.new_status == "PENDING_3RD_PARTY",
            )
            .order_by(ExceptionStatusHistory.changed_at.desc(),
                      ExceptionStatusHistory.log_id.desc())
            .first()
        )
        pause_entry.changed_at = datetime.now() - timedelta(minutes=12)
        self.db.flush()

        result = transition_exception_status(
            self.db, exception_id, "IN_PROGRESS", commit=False
        )

        self.assertGreaterEqual(result["total_paused_minutes"], 11)

    def test_resolution_requires_verification_and_nonblank_notes(self):
        exception_id = self._create_exception()

        with self.assertRaisesRegex(ValueError, "without verification"):
            resolve_exception(
                self.db,
                exception_id,
                "TEST ONLY: verified resolution.",
                verified=False,
                commit=False,
            )

        with self.assertRaisesRegex(ValueError, "Resolution notes are required"):
            resolve_exception(
                self.db,
                exception_id,
                "   ",
                verified=True,
                commit=False,
            )

    def test_resolution_rejects_caller_boolean_without_database_verification(self):
        exception_id = self._create_exception()

        with self.assertRaisesRegex(
            ValueError, "no verification record exists"
        ):
            resolve_exception(
                self.db,
                exception_id,
                "TEST ONLY: caller supplied verified=True.",
                verified=True,
                commit=False,
            )

    def test_resolution_rejects_latest_non_verified_record(self):
        exception_id = self._create_exception()
        now = datetime.now()

        self._create_verification(
            exception_id,
            "VERIFIED",
            verified_at=now - timedelta(minutes=1),
        )
        self._create_verification(
            exception_id,
            "INCONCLUSIVE",
            verified_at=now,
        )

        with self.assertRaisesRegex(
            ValueError, "latest verification is not VERIFIED"
        ):
            resolve_exception(
                self.db,
                exception_id,
                "TEST ONLY: older VERIFIED record must not win.",
                verified=True,
                commit=False,
            )

    def test_resolution_rejects_verification_for_another_shipment(self):
        exception_id = self._create_exception()
        other_shipment = (
            self.db.query(Shipment)
            .filter(Shipment.shipment_id != self.shipment.shipment_id)
            .first()
        )
        if other_shipment is None:
            self.skipTest("A second shipment is required for this regression.")

        self._create_verification(
            exception_id,
            "VERIFIED",
            shipment_id=other_shipment.shipment_id,
        )

        with self.assertRaisesRegex(
            ValueError, "verification shipment does not match"
        ):
            resolve_exception(
                self.db,
                exception_id,
                "TEST ONLY: mismatched shipment verification.",
                verified=True,
                commit=False,
            )

    def test_resolution_succeeds_with_latest_matching_verified_record(self):
        exception_id = self._create_exception()
        self._create_verification(
            exception_id,
            "VERIFIED",
            verified_at=datetime.now(),
        )

        result = resolve_exception(
            self.db,
            exception_id,
            "TEST ONLY: issue corrected and evidence checked.",
            verified=True,
            commit=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(self._get_exception(exception_id).status, "RESOLVED")
        self.assertEqual(
            self._get_exception(exception_id).resolution_notes,
            "TEST ONLY: issue corrected and evidence checked.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
