
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

    Collects shipment, event, document, validation and
    exception evidence.

    Document handling:
    - Identifies the latest version of each document type.
    - Separates current validation results from historical ones.
    - Preserves historical mismatches as historical evidence.
    - Does not mistake a corrected historical mismatch
      for a current document mismatch.
    - Identifies distinct historical mismatch patterns.
    """

    try:

        current_time = datetime.now()

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
        # 4. COLLECT RELATED EVENTS
        # --------------------------------------------------

        events = (
            db.query(ShipmentEvent)
            .filter(
                ShipmentEvent.shipment_id == shipment.shipment_id
            )
            .order_by(
                ShipmentEvent.event_id.asc()
            )
            .all()
        )

        # --------------------------------------------------
        # 5. COLLECT ALL DOCUMENT VERSIONS
        # --------------------------------------------------

        documents = (
            db.query(Document)
            .filter(
                Document.shipment_id == shipment.shipment_id
            )
            .order_by(
                Document.document_type.asc(),
                Document.version_no.desc(),
                Document.upload_date.desc(),
                Document.document_id.desc()
            )
            .all()
        )

        # --------------------------------------------------
        # 6. IDENTIFY LATEST DOCUMENT PER TYPE
        # --------------------------------------------------

        latest_documents = {}

        for document in documents:

            if document.document_type not in latest_documents:

                latest_documents[document.document_type] = document

        current_documents = list(
            latest_documents.values()
        )

        current_document_ids = {
            document.document_id
            for document in current_documents
        }

        historical_documents = [
            document
            for document in documents
            if document.document_id not in current_document_ids
        ]

        # --------------------------------------------------
        # 7. COLLECT VALIDATION HISTORY
        # --------------------------------------------------

        validations = (
            db.query(DocumentValidation)
            .filter(
                DocumentValidation.shipment_id == shipment.shipment_id
            )
            .order_by(
                DocumentValidation.validated_at.asc(),
                DocumentValidation.validation_id.asc()
            )
            .all()
        )

        # A validation belongs to the current document state
        # only when its document_id is a latest document ID
        # and its compared document is either absent or also
        # a latest document ID.

        current_validations = [
            validation
            for validation in validations
            if (
                validation.document_id in current_document_ids
                and (
                    validation.compared_document_id is None
                    or validation.compared_document_id
                    in current_document_ids
                )
            )
        ]

        historical_validations = [
            validation
            for validation in validations
            if validation not in current_validations
        ]

        # --------------------------------------------------
        # 8. IDENTIFY CURRENT AND HISTORICAL MISMATCHES
        # --------------------------------------------------

        current_mismatches = [
            validation
            for validation in current_validations
            if str(
                validation.validation_result
            ).upper() == "MISMATCH"
        ]

        historical_mismatches = [
            validation
            for validation in historical_validations
            if str(
                validation.validation_result
            ).upper() == "MISMATCH"
        ]

        # Current document statuses are also considered.

        current_status_mismatches = [
            document
            for document in current_documents
            if str(
                document.validation_status
            ).upper() == "MISMATCH"
        ]

        # --------------------------------------------------
        # 8A. IDENTIFY DISTINCT HISTORICAL MISMATCH PATTERNS
        # --------------------------------------------------

        historical_mismatch_fields = sorted({
            str(validation.field_name).strip().upper()
            for validation in historical_mismatches
        })

        # Reverse-direction validation records represent
        # the same mismatch pattern.
        #
        # Example:
        # WRONG1234567 vs TEST1234567
        # TEST1234567 vs WRONG1234567
        #
        # Sorting the values makes both records produce
        # the same pattern.

        historical_mismatch_patterns = {
            (
                str(validation.field_name).strip().upper(),
                tuple(sorted([
                    str(validation.extracted_value).strip().upper(),
                    str(validation.expected_value).strip().upper()
                ]))
            )
            for validation in historical_mismatches
        }

        historical_discrepancy_count = len(
            historical_mismatch_patterns
        )

        # --------------------------------------------------
        # 9. CHECK CURRENT DOCUMENT COMPLETENESS
        # --------------------------------------------------

        required_document_types = {
            "COMMERCIAL_INVOICE",
            "BILL_OF_LADING"
        }

        missing_document_types = (
            required_document_types
            - set(latest_documents.keys())
        )

        documents_with_extraction_issues = [
            document
            for document in current_documents
            if str(
                document.extraction_status
            ).upper() != "EXTRACTED"
        ]

        documents_with_validation_issues = [
            document
            for document in current_documents
            if str(
                document.validation_status
            ).upper() in (
                "MISMATCH",
                "INCOMPLETE",
                "NOT_VALIDATED"
            )
        ]

        current_documents_valid = (
            not missing_document_types
            and not documents_with_extraction_issues
            and not documents_with_validation_issues
        )

        # --------------------------------------------------
        # 10. INITIAL INVESTIGATION FINDINGS
        # --------------------------------------------------

        exception_type = str(
            exception.exception_type
        ).upper()

        possible_cause = "REQUIRES_MANUAL_REVIEW"

        affected_process = "LOGISTICS_OPERATIONS"

        summary = (
            f"Investigation of exception {exception_id} "
            f"collected {len(events)} shipment events, "
            f"{len(documents)} document versions and "
            f"{len(validations)} validation records."
        )

        recommended_next = (
            "Review the collected evidence and determine "
            "the appropriate corrective action."
        )

        # --------------------------------------------------
        # DOCUMENT MISMATCH
        # --------------------------------------------------

        if exception_type == "DOCUMENT_MISMATCH":

            affected_process = "DOCUMENT_VALIDATION"

            if current_mismatches or current_status_mismatches:

                mismatch_fields = sorted({
                    str(validation.field_name)
                    for validation in current_mismatches
                })

                mismatch_document_types = sorted({
                    str(document.document_type)
                    for document in current_status_mismatches
                })

                details = []

                if mismatch_fields:

                    details.append(
                        "Affected fields: "
                        + ", ".join(mismatch_fields)
                    )

                if mismatch_document_types:

                    details.append(
                        "Documents with current MISMATCH status: "
                        + ", ".join(mismatch_document_types)
                    )

                possible_cause = (
                    "CURRENT_DOCUMENT_MISMATCH"
                )

                summary = (
                    "The latest available document versions "
                    "still contain validation mismatches. "
                    + ". ".join(details)
                )

                recommended_next = (
                    "Request corrected document versions "
                    "from the responsible stakeholder and "
                    "revalidate the affected documents."
                )

            elif (
                historical_mismatches
                and current_documents_valid
            ):

                possible_cause = (
                    "HISTORICAL_DOCUMENT_MISMATCH_CORRECTED"
                )

                summary = (
                    "Historical document versions contained "
                    f"{len(historical_mismatches)} mismatch "
                    "validation records representing "
                    f"{historical_discrepancy_count} distinct "
                    "mismatch pattern(s) across "
                    f"{len(historical_mismatch_fields)} "
                    "affected field(s): "
                    + ", ".join(historical_mismatch_fields)
                    + ". However, the latest available document "
                    "versions have successful extraction and "
                    "VALID status. The historical mismatch is "
                    "not present in the current document versions."
                )

                recommended_next = (
                    "Review the correction history and verify "
                    "that the previous document mismatch "
                    "has been formally resolved."
                )

            elif historical_mismatches:

                possible_cause = (
                    "HISTORICAL_DOCUMENT_MISMATCH_WITH "
                    "_CURRENT_STATE_REQUIRING_REVIEW"
                )

                summary = (
                    "Historical document mismatches were found. "
                    "The latest document versions do not provide "
                    "enough evidence to confirm that the issue "
                    "has been corrected."
                )

                recommended_next = (
                    "Review the latest document versions, "
                    "complete extraction or validation where "
                    "necessary, and verify the correction."
                )

            else:

                possible_cause = (
                    "DOCUMENT_MISMATCH_REQUIRES_REVALIDATION"
                )

                summary = (
                    "The original document mismatch exception "
                    "was investigated, but no matching mismatch "
                    "was found in the available validation "
                    "history. Further verification is required."
                )

                recommended_next = (
                    "Run document validation against the "
                    "latest invoice and bill of lading, then "
                    "review the results."
                )

        # --------------------------------------------------
        # MISSING DOCUMENT
        # --------------------------------------------------

        elif exception_type == "MISSING_DOCUMENT":

            affected_process = "DOCUMENT_COLLECTION"

            if missing_document_types:

                possible_cause = "REQUIRED_DOCUMENT_MISSING"

                summary = (
                    "The following required document types "
                    "are missing: "
                    + ", ".join(sorted(missing_document_types))
                )

                recommended_next = (
                    "Request the missing documents from "
                    "the responsible stakeholder."
                )

            else:

                possible_cause = (
                    "REQUIRED_DOCUMENTS_CURRENTLY_AVAILABLE"
                )

                summary = (
                    "The required document types are currently "
                    "available. Their latest versions and "
                    "processing statuses were reviewed."
                )

                recommended_next = (
                    "Verify that the latest required documents "
                    "are successfully extracted and validated."
                )

        # --------------------------------------------------
        # SHIPMENT DELAY
        # --------------------------------------------------

        elif exception_type == "SHIPMENT_DELAY":

            overdue_events = [
                event
                for event in events
                if str(
                    getattr(event, "event_status", "")
                ).upper() in ("PENDING", "LATE")
                and getattr(event, "actual_time", None) is None
                and getattr(event, "expected_time", None) is not None
                and event.expected_time < current_time
            ]

            if overdue_events:

                possible_cause = (
                    "OVERDUE_SHIPMENT_MILESTONE"
                )

            else:

                possible_cause = (
                    "SHIPMENT_DELAY_REQUIRES_REVIEW"
                )

            affected_process = "SHIPMENT_MONITORING"

            summary = (
                f"Shipment delay investigated. "
                f"{len(overdue_events)} currently overdue "
                f"milestone records were identified."
            )

            recommended_next = (
                "Verify the shipment progress with the "
                "responsible logistics stakeholder."
            )

        # --------------------------------------------------
        # CUSTOMS HOLD
        # --------------------------------------------------

        elif exception_type == "CUSTOMS_HOLD":

            possible_cause = "CUSTOMS_CLEARANCE_ISSUE"

            affected_process = "CUSTOMS_CLEARANCE"

            summary = (
                "A customs hold exception was investigated. "
                "Further verification of customs clearance "
                "status is required."
            )

            recommended_next = (
                "Escalate the customs hold to the customs "
                "clearance team for review."
            )

        # --------------------------------------------------
        # MISSING MILESTONE
        # --------------------------------------------------

        elif exception_type == "MISSING_MILESTONE":

            possible_cause = (
                "SHIPMENT_MILESTONE_NOT_RECORDED"
            )

            affected_process = "SHIPMENT_MONITORING"

            recommended_next = (
                "Verify the milestone with the responsible "
                "logistics stakeholder."
            )

        # --------------------------------------------------
        # STAKEHOLDER RESPONSE DELAY
        # --------------------------------------------------

        elif exception_type == "STAKEHOLDER_RESPONSE_DELAY":

            possible_cause = (
                "STAKEHOLDER_RESPONSE_OVERDUE"
            )

            affected_process = "STAKEHOLDER_COORDINATION"

            recommended_next = (
                "Follow up with the responsible stakeholder "
                "and escalate if necessary."
            )

        # --------------------------------------------------
        # CONTAINER NOT DISCHARGED
        # --------------------------------------------------

        elif exception_type == "CONTAINER_NOT_DISCHARGED":

            possible_cause = (
                "CONTAINER_DISCHARGE_NOT_CONFIRMED"
            )

            affected_process = "PORT_OPERATIONS"

            recommended_next = (
                "Verify container discharge status with "
                "the port or terminal operator."
            )

        # --------------------------------------------------
        # 11. CREATE INVESTIGATION
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
        # 12. HELPER TO SAVE EVIDENCE
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

            sources = [
                shipment_id,
                event_id,
                document_id,
                validation_id,
                exception_id,
                risk_id,
                action_id
            ]

            if sum(
                source is not None
                for source in sources
            ) != 1:

                raise ValueError(
                    "Each evidence record must have "
                    "exactly one source ID."
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
        # 13. SHIPMENT EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="CONFIRMED_FACT",
            statement=(
                f"Shipment record exists with shipment ID "
                f"{shipment.shipment_id}, reference "
                f"{shipment.shipment_ref}, and status "
                f"{shipment.status}."
            ),
            shipment_id=shipment.shipment_id
        )

        # --------------------------------------------------
        # 14. EVENT EVIDENCE
        # --------------------------------------------------

        for event in events:

            save_evidence(
                evidence_class="CONFIRMED_FACT",
                statement=(
                    f"Shipment event ID {event.event_id} "
                    f"has status "
                    f"{getattr(event, 'event_status', 'UNKNOWN')}. "
                    f"Expected time: "
                    f"{getattr(event, 'expected_time', None)}. "
                    f"Actual time: "
                    f"{getattr(event, 'actual_time', None)}."
                ),
                event_id=event.event_id
            )

        # --------------------------------------------------
        # 15. CURRENT AND HISTORICAL DOCUMENT EVIDENCE
        # --------------------------------------------------

        for document in documents:

            is_current = (
                document.document_id in current_document_ids
            )

            version_label = (
                "CURRENT LATEST VERSION"
                if is_current
                else "HISTORICAL VERSION"
            )

            save_evidence(
                evidence_class="CONFIRMED_FACT",
                statement=(
                    f"{version_label}: Document ID "
                    f"{document.document_id}, type "
                    f"{document.document_type}, version "
                    f"{document.version_no}, extraction status "
                    f"{document.extraction_status}, validation "
                    f"status {document.validation_status}."
                ),
                document_id=document.document_id
            )

        # --------------------------------------------------
        # 16. VALIDATION EVIDENCE
        # --------------------------------------------------

        for validation in validations:

            is_current = (
                validation in current_validations
            )

            validation_status = str(
                validation.validation_result
            ).upper()

            version_label = (
                "CURRENT DOCUMENT VALIDATION"
                if is_current
                else "HISTORICAL DOCUMENT VALIDATION"
            )

            evidence_class = (
                "CONFIRMED_FACT"
                if validation_status in (
                    "MATCH",
                    "MISMATCH"
                )
                else "POSSIBLE_EXPLANATION"
            )

            compared_document_text = ""

            if validation.compared_document_id is not None:

                compared_document_text = (
                    f" Compared document ID: "
                    f"{validation.compared_document_id}."
                )

            save_evidence(
                evidence_class=evidence_class,
                statement=(
                    f"{version_label}: Validation ID "
                    f"{validation.validation_id} returned "
                    f"{validation_status} for field "
                    f"{validation.field_name}. "
                    f"Document ID: {validation.document_id}."
                    f"{compared_document_text} "
                    f"Extracted value: "
                    f"{validation.extracted_value}. "
                    f"Expected value: "
                    f"{validation.expected_value}."
                ),
                validation_id=validation.validation_id
            )

        # --------------------------------------------------
        # 17. EXCEPTION EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="CONFIRMED_FACT",
            statement=(
                f"Exception {exception.exception_id}: "
                f"{exception.exception_type}. "
                f"Description: {exception.description}. "
                f"Severity: {exception.severity}. "
                f"Current status: {exception.status}."
            ),
            exception_id=exception.exception_id
        )

        # --------------------------------------------------
        # 18. INVESTIGATION FINDING EVIDENCE
        # --------------------------------------------------

        save_evidence(
            evidence_class="POSSIBLE_EXPLANATION",
            statement=(
                f"Investigation finding: {possible_cause}. "
                f"{summary} "
                f"This finding is based on the available "
                f"records and may require human verification."
            ),
            exception_id=exception.exception_id
        )

        # --------------------------------------------------
        # 19. UPDATE EXCEPTION STATUS
        # --------------------------------------------------

        if exception.status == "OPEN":

            exception.status = "INVESTIGATING"

        # --------------------------------------------------
        # 20. COMMIT
        # --------------------------------------------------

        if commit:

            db.commit()

            db.refresh(investigation)

        else:

            db.flush()

        # --------------------------------------------------
        # 21. RETURN RESULTS
        # --------------------------------------------------

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
            "document_analysis": {
                "total_document_versions": len(documents),
                "current_document_versions": len(current_documents),
                "historical_document_versions": len(historical_documents),
                "current_validation_records": len(current_validations),
                "historical_validation_records": len(historical_validations),
                "current_mismatches": len(current_mismatches),
                "historical_mismatches": len(historical_mismatches),
                "historical_mismatch_records": len(historical_mismatches),
                "historical_mismatch_fields": historical_mismatch_fields,
                "historical_discrepancy_count": historical_discrepancy_count,
                "current_documents_valid": current_documents_valid
            },
            "evidence_count": evidence_count
        }

    except Exception:

        db.rollback()

        raise
