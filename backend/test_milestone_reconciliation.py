import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.engines.milestone_reconciliation import (
    assess_milestone_reconciliation,
)
from app.models import Document, DocumentValidation, Exception as ShipmentException


class FakeQuery:
    def __init__(self, records):
        self.records = list(records)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.records

    def first(self):
        return self.records[0] if self.records else None


class FakeDB:
    def __init__(self, documents, validations, exceptions=None):
        self.records = {
            Document: documents,
            DocumentValidation: validations,
            ShipmentException: exceptions or [],
        }

    def query(self, model):
        return FakeQuery(self.records.get(model, []))


def make_document(document_id, document_type, uploaded_at, status="VALID"):
    return SimpleNamespace(
        document_id=document_id,
        shipment_id=4,
        document_type=document_type,
        version_no=2,
        upload_date=uploaded_at,
        extraction_status="EXTRACTED",
        validation_status=status,
    )


def make_validations(invoice_id, bol_id, validated_at, results=None):
    """Create the exact required evidence matrix for the current document pair."""
    rows = []
    results = results or {}
    validation_id = 1

    def add(document_id, compared_document_id, field):
        nonlocal validation_id
        rows.append(SimpleNamespace(
            validation_id=validation_id,
            shipment_id=4,
            document_id=document_id,
            compared_document_id=compared_document_id,
            validated_at=validated_at,
            field_name=field,
            validation_result=results.get(validation_id, "MATCH"),
        ))
        validation_id += 1

    shared_fields = ["shipment_ref", "container_no", "shipper", "consignee"]
    shipment_fields = ["shipment_ref", "container_no", "shipper", "consignee"]

    for field in shared_fields:
        add(invoice_id, bol_id, field)
        add(bol_id, invoice_id, field)

    for document_id in (invoice_id, bol_id):
        for field in shipment_fields:
            add(document_id, None, field)

    return rows


class MilestoneReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.uploaded_at = datetime(2026, 11, 12, 10, 0, 0)
        self.event = SimpleNamespace(
            event_id=11,
            shipment_id=4,
            event_type="DOCUMENTATION_COMPLETE",
            event_status="INCONSISTENT",
        )
        self.documents = [
            make_document(11, "COMMERCIAL_INVOICE", self.uploaded_at),
            make_document(8, "BILL_OF_LADING", self.uploaded_at),
        ]

    def make_db(self, validations=None, exceptions=None):
        return FakeDB(
            self.documents,
            validations if validations is not None else make_validations(
                11, 8, self.uploaded_at + timedelta(minutes=1)
            ),
            exceptions,
        )

    def test_matching_current_documents_are_ready_for_human_confirmation(self):
        result = assess_milestone_reconciliation(
            self.make_db(), self.event
        )
        self.assertTrue(result["ready_for_confirmation"])
        self.assertEqual(result["event_status"], "INCONSISTENT")
        self.assertEqual(result["validation_count"], 16)

    def test_latest_document_version_is_selected(self):
        older_invoice = make_document(
            10,
            "COMMERCIAL_INVOICE",
            self.uploaded_at - timedelta(days=1)
        )
        older_invoice.version_no = 1

        # The fake query deliberately does not implement order_by().
        # The engine must still select the newest version deterministically.
        self.documents.append(older_invoice)

        result = assess_milestone_reconciliation(
            self.make_db(), self.event
        )

        self.assertTrue(result["ready_for_confirmation"])
        self.assertEqual(
            result["latest_document_ids"]["invoice"],
            11
        )

    def test_document_matching_does_not_change_event_status(self):
        original_status = self.event.event_status
        assess_milestone_reconciliation(self.make_db(), self.event)
        self.assertEqual(self.event.event_status, original_status)

    def test_stale_validation_evidence_is_rejected(self):
        stale = make_validations(
            11, 8, self.uploaded_at - timedelta(minutes=1)
        )
        result = assess_milestone_reconciliation(
            self.make_db(stale), self.event
        )
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("predate", result["reason"])

    def test_mismatching_validation_evidence_is_rejected(self):
        rows = make_validations(
            11, 8,
            self.uploaded_at + timedelta(minutes=1),
            {1: "MISMATCH"},
        )
        result = assess_milestone_reconciliation(
            self.make_db(rows), self.event
        )
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("not MATCH", result["reason"])

    def test_missing_required_field_evidence_is_rejected(self):
        rows = make_validations(
            11, 8, self.uploaded_at + timedelta(minutes=1)
        )
        rows = [
            row for row in rows
            if not (
                row.document_id == 11
                and row.compared_document_id == 8
                and row.field_name == "container_no"
            )
        ]
        result = assess_milestone_reconciliation(
            self.make_db(rows), self.event
        )
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("coverage is incomplete", result["reason"])

    def test_evidence_for_another_shipment_is_ignored(self):
        rows = make_validations(
            11, 8, self.uploaded_at + timedelta(minutes=1)
        )
        rows[0].shipment_id = 99
        result = assess_milestone_reconciliation(
            self.make_db(rows), self.event
        )
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("coverage is incomplete", result["reason"])

    def test_active_document_mismatch_exception_blocks_confirmation(self):
        active = SimpleNamespace(
            exception_id=4,
            status="OPEN",
        )
        result = assess_milestone_reconciliation(
            self.make_db(exceptions=[active]), self.event
        )
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("active DOCUMENT_MISMATCH", result["reason"])

    def test_non_documentation_event_is_not_supported(self):
        other_event = SimpleNamespace(
            event_id=12,
            event_type="VESSEL_ARRIVED",
            event_status="PENDING",
        )
        result = assess_milestone_reconciliation(
            self.make_db(), other_event
        )
        self.assertFalse(result["ready_for_confirmation"])


if __name__ == "__main__":
    unittest.main()
