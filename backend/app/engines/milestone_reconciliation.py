from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import (
    ShipmentEvent,
    Document,
    DocumentValidation,
    Exception as ShipmentException
)


# These fields are essential to identify and reconcile the shipment.
# cargo_description is checked when present, but is not a mandatory identifier.
REQUIRED_SHARED_FIELDS = [
    "shipment_ref",
    "container_no",
    "shipper",
    "consignee"
]

REQUIRED_SHIPMENT_FIELDS = [
    "shipment_ref",
    "container_no",
    "shipper",
    "consignee"
]


def _required_validation_keys(invoice_id, bill_of_lading_id):
    """Build the exact evidence keys required for the current document pair."""

    required = set()

    for field in REQUIRED_SHARED_FIELDS:
        required.add((invoice_id, bill_of_lading_id, field))
        required.add((bill_of_lading_id, invoice_id, field))

    for document_id in (invoice_id, bill_of_lading_id):
        for field in REQUIRED_SHIPMENT_FIELDS:
            required.add((document_id, None, field))

    return required


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

    # Keep the ordering deterministic even for test doubles or alternate
    # query implementations that do not apply SQLAlchemy order_by().
    documents = sorted(
        documents,
        key=lambda document: (
            document.version_no,
            document.upload_date,
            document.document_id
        ),
        reverse=True
    )

    latest = {}
    for document in documents:
        if document.shipment_id == event.shipment_id:
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

    # Query only evidence for the current invoice/BOL pair and their
    # comparisons against the shipment master record.
    current_pair_validations = or_(
        and_(
            DocumentValidation.document_id == invoice.document_id,
            DocumentValidation.compared_document_id == bill_of_lading.document_id
        ),
        and_(
            DocumentValidation.document_id == bill_of_lading.document_id,
            DocumentValidation.compared_document_id == invoice.document_id
        ),
        and_(
            DocumentValidation.document_id.in_([
                invoice.document_id,
                bill_of_lading.document_id
            ]),
            DocumentValidation.compared_document_id.is_(None)
        )
    )

    queried_validations = db.query(DocumentValidation).filter(
        DocumentValidation.shipment_id == event.shipment_id,
        current_pair_validations
    ).all()

    # Apply the same scope in Python as a defensive check. This also makes
    # the evidence boundary explicit and prevents unrelated rows from
    # satisfying the requirements if a query implementation is faulty.
    document_ids = {invoice.document_id, bill_of_lading.document_id}
    validations = [
        item for item in queried_validations
        if item.shipment_id == event.shipment_id
        and item.document_id in document_ids
        and (
            item.compared_document_id is None
            or (
                item.document_id == invoice.document_id
                and item.compared_document_id == bill_of_lading.document_id
            )
            or (
                item.document_id == bill_of_lading.document_id
                and item.compared_document_id == invoice.document_id
            )
        )
    ]

    required_keys = _required_validation_keys(
        invoice.document_id,
        bill_of_lading.document_id
    )
    actual_keys = [
        (item.document_id, item.compared_document_id, item.field_name)
        for item in validations
    ]
    actual_key_set = set(actual_keys)

    missing_keys = sorted(
        required_keys - actual_key_set,
        key=lambda key: (key[0], key[1] or 0, key[2])
    )

    duplicate_keys = sorted(
        {
            key for key in actual_keys
            if actual_keys.count(key) > 1
        },
        key=lambda key: (key[0], key[1] or 0, key[2])
    )

    if missing_keys or duplicate_keys:
        return {
            "event_id": event.event_id,
            "event_status": event.event_status,
            "ready_for_confirmation": False,
            "reason": "Required validation field coverage is incomplete or duplicated.",
            "validation_count": len(validations),
            "missing_validation_keys": [
                {
                    "document_id": key[0],
                    "compared_document_id": key[1],
                    "field": key[2]
                }
                for key in missing_keys
            ],
            "duplicate_validation_keys": [
                {
                    "document_id": key[0],
                    "compared_document_id": key[1],
                    "field": key[2]
                }
                for key in duplicate_keys
            ]
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
            "and supported by complete matching validation evidence. A manager "
            "must still confirm that the operational milestone occurred."
        ),
        "latest_document_ids": {
            "invoice": invoice.document_id,
            "bill_of_lading": bill_of_lading.document_id
        },
        "validation_count": len(validations)
    }
