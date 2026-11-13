
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Shipment,
    ShipmentEvent,
    Document,
    DocumentValidation,
    Exception as ShipmentException,
    Investigation,
    InvestigationEvidence,
)


# ==========================================================
# INVESTIGATION ENGINE
# ==========================================================

def investigate_exception(
    db: Session,
    exception_id: int,
    workflow_id: int,
    run_id: int,
    commit: bool = True
):
    """
    Investigate a logistics exception.

    Collects confirmed facts from shipment records,
    events, documents, validations and the exception.

    Identifies possible causes and stores investigation
    evidence using the actual database model structure.
    """

    try:
        # --------------------------------------------------
        # 1. FIND EXCEPTION
        # --------------------------------------------------

        exception = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.exception_id == exception_id
            )
            .first()
        )

        if not exception:
            raise LookupError(
                f"Exception {exception_id} was not found."
            )

        # --------------------------------------------------
        # 2. VALIDATE WORKFLOW AND AGENT RUN
        # --------------------------------------------------

        if workflow_id is None or run_id is None:
            raise ValueError(
                "workflow_id and run_id are required."
            )

        # --------------------------------------------------
        # 3. FIND SHIPMENT
        # --------------------------------------------------

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == exception.shipment_id
            )
            .first()
        )

        if not shipment:
            raise LookupError(
                f"Shipment {exception.shipment_id} was not found."
            )

        # --------------------------------------------------
        # 4. COLLECT RELATED RECORDS
        # --------------------------------------------------

        events = (
            db.query(ShipmentEvent)
            .filter(
                ShipmentEvent.shipment_id == shipment.shipment_id
            )
            .all()
        )

        documents = (
            db.query(Document)
            .filter(
                Document.shipment_id == shipment.shipment_id
            )
            .all()
        )

        validations = (
            db.query(DocumentValidation)
            .join(
                Document,
                DocumentValidation.document_id == Document.document_id
            )
            .filter(
                Document.shipment_id == shipment.shipment_id
            )
            .all()
        )

        # --------------------------------------------------
        # 5. IDENTIFY POSSIBLE CAUSE
        # --------------------------------------------------

        exception_type = str(exception.exception_type).upper()

        possible_cause = "REQUIRES_MANUAL_REVIEW"
        affected_process = "LOGISTICS_OPERATIONS"

        summary = (
            f"Investigation of exception {exception_id} "
            f"collected shipment, event, document and "
            f"validation evidence."
        )

        recommended_next = (
            "Review the collected evidence and determine "
            "the appropriate corrective action."
        )

        mismatches = [
            validation
            for validation in validations
            if str(
                getattr(validation, "validation_status", "")
            ).upper() == "MISMATCH"
        ]

        if exception_type == "DOCUMENT_MISMATCH":

            affected_process = "DOCUMENT_VALIDATION"

            if mismatches:
                fields = sorted({
                    str(
                        getattr(validation, "field_name", "unknown")
                    )
                    for validation in mismatches
                })

                possible_cause = (
                    "INCONSISTENT_DOCUMENT_INFORMATION: "
                    + ", ".join(fields)
                )

                summary = (
                    "Inconsistent information was found "
                    "in document validation results. "
                    "Mismatched fields: "
                    + ", ".join(fields)
                )

                recommended_next = (
                    "Request corrected shipping documents "
                    "from the responsible stakeholder."
                )

            else:
                possible_cause = (
                    "DOCUMENT_MISMATCH_REQUIRES_REVIEW"
                )

        elif exception_type == "MISSING_DOCUMENT":

            possible_cause = "REQUIRED_DOCUMENT_MISSING"
            affected_process = "DOCUMENT_COLLECTION"

            summary = (
                "A required shipment document is missing. "
                "The available shipment documents were reviewed."
            )

            recommended_next = (
                "Request the missing document from the "
                "responsible stakeholder."
            )

        elif exception_type == "SHIPMENT_DELAY":

            overdue_events = [
                event
                for event in events
                if str(
                    getattr(event, "event_status", "")
                ).upper() in ("PENDING", "LATE")
                and getattr(event, "actual_time", None) is None
            ]

            possible_cause = (
                "OVERDUE_SHIPMENT_MILESTONE"
                if overdue_events
                else "SHIPMENT_DELAY_REQUIRES_REVIEW"
            )

            affected_process = "SHIPMENT_MONITORING"

            summary = (
                f"Shipment delay investigated. "
                f"{len(overdue_events)} pending or late "
                f"milestone records were identified."
            )

            recommended_next = (
                "Contact the operations officer to verify "
                "the shipment status and expected arrival."
            )

        elif exception_type == "CUSTOMS_HOLD":

            possible_cause = "CUSTOMS_CLEARANCE_ISSUE"
            affected_process = "CUSTOMS_CLEARANCE"

            recommended_next = (
                "Escalate the customs hold for further review."
            )

        elif exception_type == "MISSING_MILESTONE":

            possible_cause = "SHIPMENT_MILESTONE_NOT_RECORDED"
            affected_process = "SHIPMENT_MONITORING"

            recommended_next = (
                "Verify the milestone with the responsible "
                "logistics stakeholder."
            )

        # --------------------------------------------------
        # 6. CREATE INVESTIGATION
        # --------------------------------------------------

        investigation = Investigation(
            exception_id=exception.exception_id,
            workflow_id=workflow_id,
            run_id=run_id,
            summary=summary,
            possible_cause=possible_cause,
            affected_process=affected_process,
            urgency=str(exception.severity).upper(),
            recommended_next=recommended_next,
            status="COMPLETED"
        )

        db.add(investigation)
        db.flush()

        # --------------------------------------------------
        # 7. HELPER TO SAVE EVIDENCE
        # --------------------------------------------------

        evidence_count = 0

        def save_evidence(
            evidence_class,
            statement,
            shipment_id=None,
            event_id=None,
            document_id=None,
            validation_id=None,
            exception_id=None,
            risk_id=None,
            action_id=None
        ):
            nonlocal evidence_count

            # Exactly one evidence source must be provided.
            sources = [
                shipment_id,
                event_id,
                document_id,
                validation_id,
                exception_id,
                risk_id,
                action_id
            ]

            if sum(source is not None for source in sources) != 1:
                raise ValueError(
                    "Each evidence record must have exactly one source ID."
                )

            evidence = InvestigationEvidence(
                investigation_id=investigation.investigation_id,
                evidence_class=evidence_class,
                statement=statement,
                shipment_id=shipment_id,
                event_id=event_id,
                document_id=document_id,
                validation_id=validation_id,
                exception_id=exception_id,
                risk_id=risk_id,
                action_id=action_id
            )

            db.add(evidence)
            evidence_count += 1

        # --------------------------------------------------
        # 8. SHIPMENT EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="CONFIRMED_FACT",
            statement=(
                f"Shipment record exists with shipment ID "
                f"{shipment.shipment_id}."
            ),
            shipment_id=shipment.shipment_id
        )

        # --------------------------------------------------
        # 9. EVENT EVIDENCE
        # --------------------------------------------------

        for event in events:

            save_evidence(
                evidence_class="CONFIRMED_FACT",
                statement=(
                    f"Shipment event ID {event.event_id} "
                    f"has status "
                    f"{getattr(event, 'event_status', 'UNKNOWN')}."
                ),
                event_id=event.event_id
            )

        # --------------------------------------------------
        # 10. DOCUMENT EVIDENCE
        # --------------------------------------------------

        for document in documents:

            save_evidence(
                evidence_class="CONFIRMED_FACT",
                statement=(
                    f"Document ID {document.document_id} "
                    f"of type "
                    f"{getattr(document, 'document_type', 'UNKNOWN')} "
                    f"exists for this shipment."
                ),
                document_id=document.document_id
            )

        # --------------------------------------------------
        # 11. VALIDATION EVIDENCE
        # --------------------------------------------------

        for validation in validations:

            validation_status = str(
                getattr(validation, "validation_status", "UNKNOWN")
            ).upper()

            evidence_class = (
                "CONFIRMED_FACT"
                if validation_status in ("MATCH", "MISMATCH")
                else "POSSIBLE_EXPLANATION"
            )

            save_evidence(
                evidence_class=evidence_class,
                statement=(
                    f"Document validation ID "
                    f"{validation.validation_id} returned "
                    f"{validation_status} for field "
                    f"{getattr(validation, 'field_name', 'UNKNOWN')}."
                ),
                validation_id=validation.validation_id
            )

        # --------------------------------------------------
        # 12. EXCEPTION EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="CONFIRMED_FACT",
            statement=(
                f"Exception {exception.exception_id}: "
                f"{exception.exception_type}. "
                f"Description: {exception.description}. "
                f"Severity: {exception.severity}."
            ),
            exception_id=exception.exception_id
        )

        # --------------------------------------------------
        # 13. POSSIBLE CAUSE EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="POSSIBLE_EXPLANATION",
            statement=(
                f"Potential cause: {possible_cause}. "
                f"This is an investigation finding and "
                f"may require human verification."
            ),
            exception_id=exception.exception_id
        )

        # --------------------------------------------------
        # 14. UPDATE EXCEPTION STATUS
        # --------------------------------------------------

        if exception.status == "OPEN":
            exception.status = "INVESTIGATING"

        # --------------------------------------------------
        # 15. COMMIT
        # --------------------------------------------------

        if commit:
            db.commit()
            db.refresh(investigation)
        else:
            db.flush()

        return {
            "message": "Investigation completed successfully.",
            "investigation_id": investigation.investigation_id,
            "exception_id": exception.exception_id,
            "shipment_id": shipment.shipment_id,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": investigation.status,
            "summary": investigation.summary,
            "possible_cause": investigation.possible_cause,
            "affected_process": investigation.affected_process,
            "recommended_next": investigation.recommended_next,
            "evidence_count": evidence_count
        }

    except Exception:
        db.rollback()
        raise
