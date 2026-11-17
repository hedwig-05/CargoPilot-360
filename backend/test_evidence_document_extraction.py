import unittest

from app.engines.evidence_document_extraction import (
    classify_other_document,
    extract_other_document_fields,
)


class EvidenceDocumentExtractionTests(unittest.TestCase):

    def test_inspection_report_is_incident_evidence(self):
        result = classify_other_document(
            "CARGO INSPECTION REPORT\nShipment Reference: CP-TEST-001"
        )
        self.assertEqual(result["document_subtype"], "INSPECTION_REPORT")
        self.assertEqual(result["evidence_role"], "INCIDENT_EVIDENCE")

    def test_credit_note_is_resolution_evidence(self):
        result = classify_other_document(
            "CREDIT NOTE\nShipment Reference: CP-TEST-001"
        )
        self.assertEqual(result["document_subtype"], "CREDIT_NOTE")
        self.assertEqual(result["evidence_role"], "RESOLUTION_EVIDENCE")

    def test_generic_tally_has_unknown_role(self):
        result = classify_other_document(
            "TALLY REPORT\nShipment Reference: CP-TEST-001"
        )
        self.assertEqual(result["document_subtype"], "TALLY_REPORT")
        self.assertIsNone(result["evidence_role"])

    def test_unrecognised_other_document_stays_unclassified(self):
        result = classify_other_document(
            "GENERAL SUPPORTING DOCUMENT\nShipment Reference: CP-TEST-001"
        )
        self.assertIsNone(result["document_subtype"])
        self.assertIsNone(result["evidence_role"])
        self.assertEqual(result["classification_confidence"], 0.0)

    def test_final_tally_is_resolution_evidence_and_scores_completeness(self):
        text = (
            "FINAL TALLY REPORT\n"
            "Shipment Reference: CP-TEST-001\n"
            "Report Date: 2026-11-17\n"
            "Expected Quantity: 120\n"
            "Received Quantity: 120\n"
        )
        result = extract_other_document_fields(text)
        self.assertEqual(result["document_subtype"], "TALLY_REPORT")
        self.assertEqual(result["evidence_role"], "RESOLUTION_EVIDENCE")
        self.assertEqual(result["extracted_fields"]["expected_quantity"], "120")
        self.assertEqual(result["extracted_fields"]["received_quantity"], "120")
        self.assertEqual(result["extraction_confidence"], 1.0)
        self.assertEqual(
            result["confidence_basis"],
            "REQUIRED_FIELD_COMPLETENESS"
        )


if __name__ == "__main__":
    unittest.main()
