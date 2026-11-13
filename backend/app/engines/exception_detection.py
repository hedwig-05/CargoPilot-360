
from datetime import datetime
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (
    ShipmentEvent,
    Shipment,
    Document
)

from app.engines.exception_lifecycle import (
    create_or_update_exception
)


# ==================================================
# DETECT SHIPMENT DELAYS
# ==================================================

def detect_shipment_delays(
    db: Session,
    commit=True,
    shipment_id: int = None
):
    """
    Detect overdue shipment milestones.

    If shipment_id is provided:
        Only monitor that shipment.

    If shipment_id is None:
        Monitor all shipments.

    Groups overdue milestones by shipment so that
    one SHIPMENT_DELAY exception is created or
    updated per shipment.
    """

    current_time = datetime.now()

    # Find overdue shipment events.
    query = db.query(ShipmentEvent).filter(
        ShipmentEvent.event_status.in_(["PENDING", "LATE"]),
        ShipmentEvent.expected_time < current_time,
        ShipmentEvent.actual_time.is_(None)
    )

    # Optional shipment-specific filtering.
    if shipment_id is not None:
        query = query.filter(
            ShipmentEvent.shipment_id == shipment_id
        )

    overdue_events = (
        query
        .order_by(
            ShipmentEvent.shipment_id,
            ShipmentEvent.expected_time
        )
        .all()
    )

    # Group overdue events by shipment ID.
    events_by_shipment = defaultdict(list)

    for event in overdue_events:
        events_by_shipment[event.shipment_id].append(event)

    detected_count = 0
    updated_count = 0
    skipped_count = 0

    try:

        for current_shipment_id, events in events_by_shipment.items():

            # Build one description containing every
            # overdue milestone for this shipment.
            milestone_details = []

            for event in events:
                milestone_details.append(
                    f"{event.event_type} "
                    f"(Event ID: {event.event_id}, "
                    f"Expected: {event.expected_time})"
                )

            description = (
                "The following shipment milestones "
                "are overdue and have not been completed: "
                + "; ".join(milestone_details)
            )

            # Link the event only when there is exactly
            # one overdue milestone.
            event_id = (
                events[0].event_id
                if len(events) == 1
                else None
            )

            result = create_or_update_exception(
                db=db,
                shipment_id=current_shipment_id,
                exception_type="SHIPMENT_DELAY",
                description=description,
                severity="HIGH",
                event_id=event_id,
                detected_by="MONITORING_AGENT",
                commit=False
            )

            operation = result["operation"]

            if operation == "CREATED":
                detected_count += 1

            elif operation == "UPDATED":
                updated_count += 1

            elif operation == "SKIPPED":
                skipped_count += 1

        if commit:
            db.commit()
        else:
            db.flush()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Shipment delay detection completed",
        "overdue_events_found": len(overdue_events),
        "shipments_processed": len(events_by_shipment),
        "exceptions_created": detected_count,
        "exceptions_updated": updated_count,
        "exceptions_skipped": skipped_count
    }


# ==================================================
# DETECT MISSING DOCUMENTS
# ==================================================

def detect_missing_documents(
    db: Session,
    commit=True,
    shipment_id: int = None
):
    """
    Detect shipments missing required documents.

    If shipment_id is provided:
        Only check that shipment.

    If shipment_id is None:
        Check all shipments.

    Collects all missing document types for each
    shipment and creates or updates one exception.
    """

    required_documents = [
        "COMMERCIAL_INVOICE",
        "BILL_OF_LADING"
    ]

    detected_count = 0
    updated_count = 0
    skipped_count = 0
    missing_count = 0

    # Retrieve shipments.
    query = db.query(Shipment)

    # Optional shipment-specific filtering.
    if shipment_id is not None:
        query = query.filter(
            Shipment.shipment_id == shipment_id
        )

    shipments = query.all()

    try:

        for shipment in shipments:

            missing_documents = []

            for document_type in required_documents:

                existing_document = (
                    db.query(Document)
                    .filter(
                        Document.shipment_id == shipment.shipment_id,
                        Document.document_type == document_type
                    )
                    .first()
                )

                if not existing_document:
                    missing_documents.append(document_type)

            if not missing_documents:
                continue

            missing_count += len(missing_documents)

            missing_list = ", ".join(missing_documents)

            description = (
                f"Required documents {missing_list} "
                f"are missing for shipment "
                f"{shipment.shipment_ref}."
            )

            result = create_or_update_exception(
                db=db,
                shipment_id=shipment.shipment_id,
                exception_type="MISSING_DOCUMENT",
                description=description,
                severity="HIGH",
                detected_by="MONITORING_AGENT",
                commit=False
            )

            operation = result["operation"]

            if operation == "CREATED":
                detected_count += 1

            elif operation == "UPDATED":
                updated_count += 1

            elif operation == "SKIPPED":
                skipped_count += 1

        if commit:
            db.commit()
        else:
            db.flush()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Missing document detection completed",
        "shipments_checked": len(shipments),
        "missing_documents_found": missing_count,
        "exceptions_created": detected_count,
        "exceptions_updated": updated_count,
        "exceptions_skipped": skipped_count
    }
