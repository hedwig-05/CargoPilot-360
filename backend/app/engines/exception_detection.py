
from datetime import datetime
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (
    ShipmentEvent,
    Shipment,
    Document,
    Exception as ShipmentException,
)

from app.engines.exception_lifecycle import (
    create_or_update_exception,
    EXPECTED_ARRIVAL,
    OVERDUE_MILESTONE,
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
        ShipmentEvent.event_status.in_(["PENDING", "LATE", "INCONSISTENT"]),
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
                "are overdue or require reconciliation and have not been completed: "
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
                commit=False,
                source_key=OVERDUE_MILESTONE,
                source_evidence={
                    "event_ids": [event.event_id for event in events],
                    "events": [
                        {
                            "event_id": event.event_id,
                            "event_type": event.event_type,
                            "expected_time": (
                                event.expected_time.isoformat()
                                if event.expected_time else None
                            ),
                            "event_status": event.event_status,
                        }
                        for event in events
                    ],
                },
                source_active=True,
            )

            operation = result["operation"]

            if operation == "CREATED":
                detected_count += 1

            elif operation == "UPDATED":
                updated_count += 1

            elif operation == "SKIPPED":
                skipped_count += 1

        # Reconcile previously active milestone sources that no longer
        # have any overdue events. Do not create exceptions during clearing.
        shipment_query = db.query(Shipment)
        if shipment_id is not None:
            shipment_query = shipment_query.filter(
                Shipment.shipment_id == shipment_id
            )
        monitored_shipments = shipment_query.all()

        for shipment in monitored_shipments:
            if events_by_shipment.get(shipment.shipment_id):
                continue
            existing = (
                db.query(ShipmentException)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type == "SHIPMENT_DELAY",
                    ShipmentException.status.in_([
                        "OPEN", "INVESTIGATING", "AWAITING_APPROVAL",
                        "IN_PROGRESS", "AWAITING_RESPONSE", "PENDING_3RD_PARTY",
                    ]),
                )
                .with_for_update()
                .first()
            )
            sources = existing.sources if existing and isinstance(existing.sources, dict) else {}
            source = sources.get(OVERDUE_MILESTONE)
            if not isinstance(source, dict) or not source.get("active", False):
                continue

            result = create_or_update_exception(
                db=db,
                shipment_id=shipment.shipment_id,
                exception_type="SHIPMENT_DELAY",
                description=existing.description or "Shipment delay.",
                severity=source.get("severity", "HIGH"),
                detected_by="MONITORING_AGENT",
                commit=False,
                source_key=OVERDUE_MILESTONE,
                source_evidence={
                    "event_ids": [],
                    "events": [],
                    "cleared_reason": "NO_OVERDUE_MILESTONES",
                },
                source_active=False,
            )
            if result["operation"] == "UPDATED":
                updated_count += 1

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
# DETECT SHIPMENT-LEVEL EXPECTED ARRIVAL DELAYS
# ==================================================

def detect_expected_arrival_delays(
    db: Session,
    commit=True,
    shipment_id: int = None
):
    """
    Detect overdue shipment-level ETAs independently of milestone events.

    Existing EXPECTED_ARRIVAL evidence is cleared when the ETA is no longer
    overdue or the shipment has arrived/reached a terminal state. Clearing is
    evidence only; it never resolves the exception.
    """
    current_time = datetime.now()
    query = db.query(Shipment).filter(
        Shipment.status.notin_(["DELIVERED", "CANCELLED"])
    )
    if shipment_id is not None:
        query = query.filter(Shipment.shipment_id == shipment_id)

    shipments = query.order_by(Shipment.shipment_id).all()
    detected_count = 0
    updated_count = 0
    cleared_count = 0
    unchanged_count = 0

    try:
        for shipment in shipments:
            overdue = (
                shipment.actual_arrival is None
                and shipment.expected_arrival is not None
                and shipment.expected_arrival < current_time
            )
            evidence = {
                "expected_arrival": (
                    shipment.expected_arrival.isoformat()
                    if shipment.expected_arrival else None
                ),
                "actual_arrival": (
                    shipment.actual_arrival.isoformat()
                    if shipment.actual_arrival else None
                ),
                "shipment_status": shipment.status,
                "on_hold": shipment.status == "ON_HOLD",
                "observed_at": current_time.isoformat(),
            }

            if overdue:
                result = create_or_update_exception(
                    db=db,
                    shipment_id=shipment.shipment_id,
                    exception_type="SHIPMENT_DELAY",
                    description=(
                        f"Shipment {shipment.shipment_ref} has passed its "
                        "expected arrival time without a recorded arrival."
                    ),
                    severity="HIGH",
                    detected_by="MONITORING_AGENT",
                    commit=False,
                    source_key=EXPECTED_ARRIVAL,
                    source_evidence=evidence,
                    source_active=True,
                )
                operation = result["operation"]
                if operation == "CREATED":
                    detected_count += 1
                elif operation == "UPDATED":
                    updated_count += 1
                else:
                    unchanged_count += 1
                continue

            # Do not create an exception merely to record an inactive source.
            existing = (
                db.query(ShipmentException)
                .filter(
                    ShipmentException.shipment_id == shipment.shipment_id,
                    ShipmentException.exception_type == "SHIPMENT_DELAY",
                    ShipmentException.status.in_([
                        "OPEN", "INVESTIGATING", "AWAITING_APPROVAL",
                        "IN_PROGRESS", "AWAITING_RESPONSE", "PENDING_3RD_PARTY",
                    ]),
                )
                .with_for_update()
                .first()
            )
            sources = existing.sources if existing and isinstance(existing.sources, dict) else {}
            source = sources.get(EXPECTED_ARRIVAL)
            if not isinstance(source, dict) or not source.get("active", False):
                unchanged_count += 1
                continue

            result = create_or_update_exception(
                db=db,
                shipment_id=shipment.shipment_id,
                exception_type="SHIPMENT_DELAY",
                description=existing.description or "Shipment delay.",
                severity=source.get("severity", "HIGH"),
                detected_by="MONITORING_AGENT",
                commit=False,
                source_key=EXPECTED_ARRIVAL,
                source_evidence=evidence,
                source_active=False,
            )
            if result["operation"] == "UPDATED":
                cleared_count += 1
            else:
                unchanged_count += 1

        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Expected-arrival delay detection completed",
        "shipments_checked": len(shipments),
        "exceptions_created": detected_count,
        "exceptions_updated": updated_count,
        "sources_cleared": cleared_count,
        "unchanged": unchanged_count,
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
