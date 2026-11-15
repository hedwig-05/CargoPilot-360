from sqlalchemy.orm import Session

from app.models import (
    ShipmentEvent,
    Document,
    DocumentValidation,
    Exception as ShipmentException
)


REQUIRED_VALIDATION_COUNT = 13


def assess_milestone_reconciliation(
    db: Session,
    event: ShipmentEvent
):
    """
    Assess whether a DOCUMENTATION_COMPLETE milestone has
    sufficient current document evidence for human confirmation.

    This function is deliberately read-only. Matching documents
    do not prove that an operational milestone actually occurred.
    """

    if event.event_type != "DOCUMENTATION_COMPLETE":
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Only DOCUMENTATION_COMPLETE milestones are supported."
        }

    documents = (
        db.query(Document)
        .filter(
            Document.shipment_id == event.shipment_id,
            Document.document_type.in_([
                "COMMERCIAL_INVOICE",
                "BILL_OF_LADING"
            ])
        )
        .order_by(
            Document.version_no.desc(),
            Document.upload_date.desc(),
            Document.document_id.desc()
        )
        .all()
    )

    latest = {}
    for document in documents:
        latest.setdefault(document.document_type, document)

    invoice = latest.get("COMMERCIAL_INVOICE")
    bill_of_lading = latest.get("BILL_OF_LADING")

    if invoice is None or bill_of_lading is None:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Both a commercial invoice and bill of lading are required.",
            "latest_document_ids": {
                "invoice": invoice.document_id if invoice else None,
                "bill_of_lading": bill_of_lading.document_id if bill_of_lading else None
            }
        }

    if (
        invoice.extraction_status != "EXTRACTED"
        or bill_of_lading.extraction_status != "EXTRACTED"
    ):
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Both latest documents must be successfully extracted."
        }

    if (
        invoice.validation_status != "VALID"
        or bill_of_lading.validation_status != "VALID"
    ):
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Both latest documents must have VALID validation status.",
            "document_statuses": {
                "invoice": invoice.validation_status,
                "bill_of_lading": bill_of_lading.validation_status
            }
        }

    validations = db.query(DocumentValidation).filter(
        DocumentValidation.shipment_id == event.shipment_id,
        DocumentValidation.document_id.in_([
            invoice.document_id,
            bill_of_lading.document_id
        ])
    ).all()

    if len(validations) < REQUIRED_VALIDATION_COUNT:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Fresh validation evidence is incomplete.",
            "validation_count": len(validations),
            "required_validation_count": REQUIRED_VALIDATION_COUNT
        }

    latest_upload_time = max(
        invoice.upload_date,
        bill_of_lading.upload_date
    )

    stale_validations = [
        item.validation_id
        for item in validations
        if item.validated_at is None
        or item.validated_at < latest_upload_time
    ]

    if stale_validations:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Validation records predate the latest uploaded document version.",
            "stale_validation_ids": stale_validations
        }

    non_matching = [
        {
            "validation_id": item.validation_id,
            "field": item.field_name,
            "result": item.validation_result
        }
        for item in validations
        if item.validation_result != "MATCH"
    ]

    if non_matching:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "One or more document validations are not MATCH.",
            "non_matching_validations": non_matching
        }

    active_exception = db.query(ShipmentException).filter(
        ShipmentException.shipment_id == event.shipment_id,
        ShipmentException.exception_type == "DOCUMENT_MISMATCH",
        ShipmentException.status.notin_(["RESOLVED", "CLOSED"])
    ).first()

    if active_exception:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "An active DOCUMENT_MISMATCH exception still exists.",
            "active_exception_id": active_exception.exception_id
        }

    return {
        "event_id": event.event_id,
        "shipment_id": event.shipment_id,
        "event_type": event.event_type,
        "event_status": event.event_status,
        "ready_for_confirmation": True,
        "reason": (
            "Latest invoice and bill of lading are extracted, valid, "
            "and supported by matching validation records. A manager "
            "must still confirm that the operational milestone occurred."
        ),
        "latest_document_ids": {
            "invoice": invoice.document_id,
            "bill_of_lading": bill_of_lading.document_id
        },
        "validation_count": len(validations)
    }
