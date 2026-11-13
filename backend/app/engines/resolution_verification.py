
import re
import uuid

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Exception as ShipmentException,
    Shipment,
    ShipmentEvent,
    Document,
    DocumentValidation,
    AgentWorkflow,
    AgentRun,
    ResolutionVerification,
    AuditLog
)

from app.engines.exception_lifecycle import resolve_exception


# ==========================================================
# SUPPORTED VERIFICATION TYPES
# ==========================================================

SUPPORTED_EXCEPTION_TYPES = [
    "DOCUMENT_MISMATCH",
    "SHIPMENT_DELAY",
    "MISSING_DOCUMENT"
]


# ==========================================================
# HELPER: CREATE VERIFICATION WORKFLOW
# ==========================================================

def create_verification_workflow(
    db: Session,
    exception: ShipmentException,
    triggered_by: int = None
):

    workflow = AgentWorkflow(
        workflow_public_id=str(uuid.uuid4()),
        thread_id=str(uuid.uuid4()),
        shipment_id=exception.shipment_id,
        exception_id=exception.exception_id,
        trigger_type="MANUAL",
        trigger_ref=f"RESOLUTION_VERIFICATION_{exception.exception_id}",
        graph_name="cargopilot_main",
        status="RUNNING",
        current_node="RESOLUTION_VERIFICATION",
        triggered_by=triggered_by
    )

    db.add(workflow)
    db.flush()

    return workflow


# ==========================================================
# HELPER: CREATE VERIFICATION AGENT RUN
# ==========================================================

def create_verification_run(
    db: Session,
    workflow: AgentWorkflow,
    exception: ShipmentException
):

    last_run = (
        db.query(AgentRun)
        .filter(
            AgentRun.workflow_id == workflow.workflow_id
        )
        .order_by(AgentRun.step_no.desc())
        .first()
    )

    next_step = (
        last_run.step_no + 1
        if last_run
        else 1
    )

    run = AgentRun(
        run_public_id=str(uuid.uuid4()),
        workflow_id=workflow.workflow_id,
        parent_run_id=None,
        step_no=next_step,
        agent_type="VERIFICATION",
        node_name="resolution_verification",
        input_data={
            "exception_id": exception.exception_id,
            "exception_type": exception.exception_type
        },
        execution_status="PROCESSING"
    )

    db.add(run)
    db.flush()

    return run


# ==========================================================
# HELPER: GET ORIGINAL MISMATCH FIELDS
# ==========================================================

def get_original_mismatch_fields(
    exception: ShipmentException
):

    description = exception.description or ""

    marker = "Affected fields:"

    if marker not in description:
        return []

    remaining = description.split(marker, 1)[1]

    remaining = remaining.split("Details:", 1)[0]

    fields = [
        field.strip().rstrip(".").strip()
        for field in remaining.split(",")
        if field.strip().rstrip(".").strip()
    ]

    return fields


# ==========================================================
# HELPER: VERIFY DOCUMENT MISMATCH
# ==========================================================

def verify_document_mismatch(
    db: Session,
    exception: ShipmentException,
    shipment: Shipment
):

    # --------------------------------------------------
    # 1. DEFINE THE FIELDS TO VERIFY
    # --------------------------------------------------

    shared_fields = [
        "shipment_ref",
        "container_no",
        "shipper",
        "consignee",
        "cargo_description"
    ]

    shipment_fields = [
        "shipment_ref",
        "container_no",
        "shipper",
        "consignee"
    ]

    results = []
    mismatches = []
    missing_evidence = []

    def normalize(value):

        if value is None:
            return None

        return " ".join(
            str(value).lower().strip().split()
        )

    # --------------------------------------------------
    # 2. IDENTIFY THE ORIGINAL INVOICE
    # --------------------------------------------------

    if not exception.document_id:

        return {
            "status": "INCONCLUSIVE",
            "summary": "The original document ID is unavailable.",
            "validation_results": []
        }

    original_invoice = (
        db.query(Document)
        .filter(
            Document.document_id == exception.document_id,
            Document.shipment_id == shipment.shipment_id
        )
        .first()
    )

    if (
        original_invoice is None
        or original_invoice.document_type != "COMMERCIAL_INVOICE"
    ):

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The original exception document could not "
                "be identified as a commercial invoice."
            ),
            "validation_results": []
        }

    # --------------------------------------------------
    # 3. GET THE LATEST DOCUMENT VERSIONS
    # --------------------------------------------------

    documents = (
        db.query(Document)
        .filter(
            Document.shipment_id == shipment.shipment_id,
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

    latest_documents = {}

    for document in documents:

        if document.document_type not in latest_documents:

            latest_documents[document.document_type] = document

    invoice = latest_documents.get("COMMERCIAL_INVOICE")

    bill_of_lading = latest_documents.get("BILL_OF_LADING")

    if invoice is None or bill_of_lading is None:

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The latest invoice or bill of lading is missing."
            ),
            "validation_results": []
        }

    # --------------------------------------------------
    # 4. REQUIRE A NEWER CORRECTED INVOICE
    # --------------------------------------------------

    if invoice.document_id == original_invoice.document_id:

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "No corrected commercial invoice has been uploaded. "
                "The original invoice is still the latest version."
            ),
            "validation_results": []
        }

    if invoice.version_no <= original_invoice.version_no:

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The latest invoice does not have a version "
                "number greater than the original invoice."
            ),
            "validation_results": []
        }

    if invoice.upload_date <= original_invoice.upload_date:

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The latest invoice was not uploaded after "
                "the original invoice."
            ),
            "validation_results": []
        }

    # --------------------------------------------------
    # 5. CHECK DOCUMENT EXTRACTION STATUS
    # --------------------------------------------------

    if (
        invoice.extraction_status != "EXTRACTED"
        or bill_of_lading.extraction_status != "EXTRACTED"
    ):

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The latest invoice or bill of lading "
                "has not completed document extraction."
            ),
            "validation_results": []
        }

    verification_documents = {
        "invoice": invoice,
        "bill_of_lading": bill_of_lading
    }

    # --------------------------------------------------
    # 6. HELPER: CHECK VALIDATION RECORD
    # --------------------------------------------------

    def record_check(
        check_name,
        document_id,
        compared_document_id,
        field_name
    ):

        validation = (
            db.query(DocumentValidation)
            .filter(
                DocumentValidation.document_id == document_id,
                DocumentValidation.compared_document_id
                == compared_document_id,
                DocumentValidation.shipment_id
                == shipment.shipment_id,
                DocumentValidation.field_name == field_name
            )
            .order_by(
                DocumentValidation.validated_at.desc(),
                DocumentValidation.validation_id.desc()
            )
            .first()
        )

        if validation is None:

            missing_evidence.append(check_name)

            results.append({
                "check": check_name,
                "field": field_name,
                "result": "MISSING",
                "explanation": (
                    "No validation record was found."
                )
            })

            return

        # Determine the upload date that the validation
        # must be newer than.

        involved_documents = [
            verification_documents["invoice"]
            if document_id == invoice.document_id
            else verification_documents["bill_of_lading"]
        ]

        if compared_document_id is not None:

            involved_documents.append(
                verification_documents["invoice"]
                if compared_document_id == invoice.document_id
                else verification_documents["bill_of_lading"]
            )

        latest_required_upload_date = max(
            document.upload_date
            for document in involved_documents
        )

        if validation.validated_at < latest_required_upload_date:

            missing_evidence.append(check_name)

            results.append({
                "check": check_name,
                "field": field_name,
                "result": "STALE",
                "explanation": (
                    "The validation record was created before "
                    "the latest involved document was uploaded."
                )
            })

            return

        result = validation.validation_result

        results.append({
            "check": check_name,
            "field": field_name,
            "result": result,
            "explanation": validation.explanation
        })

        if result == "MISMATCH":

            mismatches.append(check_name)

        elif result in ["MISSING", "UNCERTAIN"]:

            missing_evidence.append(check_name)

    # --------------------------------------------------
    # 7. VERIFY DIRECT EXTRACTED VALUES
    # --------------------------------------------------

    invoice_fields = invoice.extracted_fields or {}

    bol_fields = bill_of_lading.extracted_fields or {}

    shipment_values = {
        "shipment_ref": shipment.shipment_ref,
        "container_no": shipment.container_no,
        "shipper": shipment.shipper,
        "consignee": shipment.consignee
    }

    for field_name in shared_fields:

        invoice_value = invoice_fields.get(field_name)

        bol_value = bol_fields.get(field_name)

        if invoice_value is None or bol_value is None:

            missing_evidence.append(
                f"DIRECT_DOCUMENT_COMPARISON_{field_name}"
            )

        elif normalize(invoice_value) != normalize(bol_value):

            mismatches.append(
                f"INVOICE_VS_BOL_{field_name}"
            )

        if field_name in shipment_fields:

            shipment_value = shipment_values[field_name]

            for document_name, document_value in [
                ("INVOICE", invoice_value),
                ("BOL", bol_value)
            ]:

                check_name = (
                    f"{document_name}_VS_SHIPMENT_{field_name}"
                )

                if document_value is None or shipment_value is None:

                    missing_evidence.append(check_name)

                elif normalize(document_value) != normalize(shipment_value):

                    mismatches.append(check_name)

    # --------------------------------------------------
    # 8. VERIFY FRESH DOCUMENT-TO-SHIPMENT RECORDS
    # --------------------------------------------------

    for document_name, document in [
        ("INVOICE", invoice),
        ("BOL", bill_of_lading)
    ]:

        for field_name in shipment_fields:

            record_check(
                check_name=f"{document_name}_VS_SHIPMENT_{field_name}",
                document_id=document.document_id,
                compared_document_id=None,
                field_name=field_name
            )

    # --------------------------------------------------
    # 9. VERIFY FRESH INVOICE-TO-BOL RECORDS
    # --------------------------------------------------

    for field_name in shared_fields:

        record_check(
            check_name=f"INVOICE_VS_BOL_{field_name}",
            document_id=invoice.document_id,
            compared_document_id=bill_of_lading.document_id,
            field_name=field_name
        )

        record_check(
            check_name=f"BOL_VS_INVOICE_{field_name}",
            document_id=bill_of_lading.document_id,
            compared_document_id=invoice.document_id,
            field_name=field_name
        )

    # --------------------------------------------------
    # 10. DETERMINE VERIFICATION STATUS
    # --------------------------------------------------

    if mismatches:

        status = "NOT_VERIFIED"

        summary = (
            "The latest documents still contain one or more "
            "confirmed inconsistencies."
        )

    elif missing_evidence:

        status = "INCONCLUSIVE"

        summary = (
            "The corrected invoice was identified, but some "
            "required fresh validation evidence is missing "
            "or incomplete."
        )

    else:

        status = "VERIFIED"

        summary = (
            "The corrected invoice, bill of lading and shipment "
            "master agree across all required fields. Fresh "
            "validation records confirm the correction."
        )

    return {
        "status": status,
        "summary": summary,
        "validation_results": results,
        "mismatches": mismatches,
        "missing_evidence": missing_evidence,
        "original_invoice_id": original_invoice.document_id,
        "corrected_invoice_id": invoice.document_id,
        "corrected_invoice_version": invoice.version_no,
        "bill_of_lading_id": bill_of_lading.document_id
    }


# ==========================================================
# HELPER: VERIFY SHIPMENT DELAY
# ==========================================================

def verify_shipment_delay(
    db: Session,
    exception: ShipmentException,
    shipment: Shipment
):

    """
    Verify every overdue milestone associated
    with the original SHIPMENT_DELAY exception.

    VERIFIED:
        Every affected milestone is completed
        with an actual completion timestamp.

    NOT_VERIFIED:
        At least one affected milestone remains
        overdue and incomplete.

    INCONCLUSIVE:
        Required event evidence is missing
        or inconsistent.
    """

    # --------------------------------------------------
    # 1. IDENTIFY ORIGINAL EVENT IDS
    # --------------------------------------------------

    description = exception.description or ""

    event_matches = re.findall(
        r"([A-Z_]+)\s+\(Event ID:\s*(\d+)",
        description
    )

    affected_events = {}

    for event_type, event_id in event_matches:

        affected_events[int(event_id)] = event_type

    # Fallback to directly associated event.

    if not affected_events and exception.event_id:

        affected_events[exception.event_id] = None

    if not affected_events:

        return {
            "status": "INCONCLUSIVE",
            "summary": (
                "The original overdue milestone IDs "
                "could not be identified."
            ),
            "validation_results": [],
            "missing_evidence": [
                "ORIGINAL_OVERDUE_EVENT_IDS"
            ]
        }

    # --------------------------------------------------
    # 2. RETRIEVE AND CHECK ORIGINAL EVENTS
    # --------------------------------------------------

    results = []

    unresolved_events = []

    missing_evidence = []

    inconsistent_events = []

    for event_id, expected_event_type in affected_events.items():

        event = (
            db.query(ShipmentEvent)
            .filter(
                ShipmentEvent.event_id == event_id,
                ShipmentEvent.shipment_id == shipment.shipment_id
            )
            .first()
        )

        # ----------------------------------------------
        # EVENT NOT FOUND
        # ----------------------------------------------

        if event is None:

            missing_evidence.append(event_id)

            results.append({
                "event_id": event_id,
                "expected_event_type": expected_event_type,
                "result": "MISSING",
                "explanation": (
                    "The original overdue shipment event "
                    "could not be found."
                )
            })

            continue

        # ----------------------------------------------
        # CHECK EVENT TYPE
        # ----------------------------------------------

        if (
            expected_event_type is not None
            and event.event_type != expected_event_type
        ):

            inconsistent_events.append(event_id)

            results.append({
                "event_id": event_id,
                "event_type": event.event_type,
                "result": "INCONSISTENT",
                "explanation": (
                    "The event type does not match "
                    "the original exception description."
                )
            })

            continue

        # ----------------------------------------------
        # CHECK COMPLETION EVIDENCE
        # ----------------------------------------------

        if (
            event.event_status == "COMPLETED"
            and event.actual_time is not None
        ):

            results.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "expected_time": event.expected_time.isoformat(),
                "actual_time": event.actual_time.isoformat(),
                "event_status": event.event_status,
                "source": event.source,
                "result": "COMPLETED",
                "explanation": (
                    "The original overdue milestone "
                    "has been completed with an actual "
                    "completion timestamp."
                )
            })

        elif (
            event.event_status in ["PENDING", "LATE"]
            and event.actual_time is None
            and event.expected_time < datetime.now()
        ):

            unresolved_events.append(event.event_id)

            results.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "expected_time": event.expected_time.isoformat(),
                "actual_time": None,
                "event_status": event.event_status,
                "result": "NOT_COMPLETED",
                "explanation": (
                    "The original milestone remains "
                    "overdue without an actual completion time."
                )
            })

        else:

            inconsistent_events.append(event.event_id)

            results.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "expected_time": event.expected_time.isoformat(),
                "actual_time": (
                    event.actual_time.isoformat()
                    if event.actual_time
                    else None
                ),
                "event_status": event.event_status,
                "result": "INCONSISTENT",
                "explanation": (
                    "The milestone status and actual "
                    "completion timestamp do not provide "
                    "sufficient consistent evidence."
                )
            })

    # --------------------------------------------------
    # 3. DETERMINE FINAL VERIFICATION STATUS
    # --------------------------------------------------

    if unresolved_events:

        status = "NOT_VERIFIED"

        summary = (
            "One or more original shipment milestones "
            "remain overdue and incomplete."
        )

    elif missing_evidence or inconsistent_events:

        status = "INCONCLUSIVE"

        summary = (
            "The shipment delay could not be fully verified "
            "because some original milestone evidence "
            "is missing or inconsistent."
        )

    else:

        status = "VERIFIED"

        summary = (
            "All original overdue shipment milestones "
            "have been completed with actual completion "
            "timestamps."
        )

    return {
        "status": status,
        "summary": summary,
        "validation_results": results,
        "unresolved_events": unresolved_events,
        "missing_evidence": missing_evidence,
        "inconsistent_events": inconsistent_events,
        "total_events_checked": len(affected_events)
    }


def verify_missing_document(
    db: Session,
    exception: ShipmentException,
    shipment: Shipment
):
    """
    Verify whether all required shipment documents
    have been uploaded and successfully extracted.

    The latest version of each required document
    is used for verification.
    """

    required_document_types = [
        "COMMERCIAL_INVOICE",
        "BILL_OF_LADING"
    ]

    documents = (
        db.query(Document)
        .filter(
            Document.shipment_id == shipment.shipment_id,
            Document.document_type.in_(
                required_document_types
            )
        )
        .order_by(
            Document.version_no.desc(),
            Document.upload_date.desc(),
            Document.document_id.desc()
        )
        .all()
    )

    # Keep only the latest version of each document type.
    latest_documents = {}

    for document in documents:

        if document.document_type not in latest_documents:
            latest_documents[document.document_type] = document

    validation_results = []
    missing_documents = []
    incomplete_documents = []

    for document_type in required_document_types:

        document = latest_documents.get(document_type)

        # ------------------------------------------
        # CHECK 1: DOCUMENT EXISTS
        # ------------------------------------------

        if document is None:

            missing_documents.append(document_type)

            validation_results.append({
                "document_type": document_type,
                "result": "MISSING",
                "explanation": (
                    "The required document has not "
                    "been uploaded for this shipment."
                )
            })

            continue

        # ------------------------------------------
        # CHECK 2: EXTRACTION COMPLETED
        # ------------------------------------------

        if document.extraction_status != "EXTRACTED":

            incomplete_documents.append(document_type)

            validation_results.append({
                "document_type": document_type,
                "document_id": document.document_id,
                "version_no": document.version_no,
                "extraction_status": document.extraction_status,
                "result": "NOT_EXTRACTED",
                "explanation": (
                    "The latest document version has not "
                    "been successfully extracted."
                )
            })

            continue

        # ------------------------------------------
        # CHECK 3: EXTRACTED FIELDS ARE AVAILABLE
        # ------------------------------------------

        extracted_fields = document.extracted_fields

        if not isinstance(extracted_fields, dict) or not extracted_fields:

            incomplete_documents.append(document_type)

            validation_results.append({
                "document_type": document_type,
                "document_id": document.document_id,
                "version_no": document.version_no,
                "result": "NO_EXTRACTED_FIELDS",
                "explanation": (
                    "The document extraction status is EXTRACTED, "
                    "but no structured fields are available."
                )
            })

            continue

        validation_results.append({
            "document_type": document_type,
            "document_id": document.document_id,
            "version_no": document.version_no,
            "extraction_status": document.extraction_status,
            "fields_found": len(extracted_fields),
            "result": "EXTRACTED",
            "explanation": (
                "The latest document version exists "
                "and has successfully extracted fields."
            )
        })

    # ----------------------------------------------
    # DETERMINE OVERALL VERIFICATION RESULT
    # ----------------------------------------------

    if missing_documents:

        return {
            "status": "NOT_VERIFIED",
            "summary": (
                "Required shipment documents are still missing: "
                + ", ".join(missing_documents)
                + "."
            ),
            "validation_results": validation_results
        }

    if incomplete_documents:

        return {
            "status": "NOT_VERIFIED",
            "summary": (
                "Required documents exist, but their latest "
                "versions have not completed successful extraction: "
                + ", ".join(incomplete_documents)
                + "."
            ),
            "validation_results": validation_results
        }

    return {
        "status": "VERIFIED",
        "summary": (
            "All required shipment documents are uploaded "
            "and their latest versions have successfully "
            "completed document extraction."
        ),
        "validation_results": validation_results
    }


# ==========================================================
# HELPER: CREATE VERIFICATION AUDIT LOG
# ==========================================================

def create_verification_audit_log(
    db: Session,
    verification: ResolutionVerification
):

    audit = AuditLog(
        actor_type="AGENT",
        actor_name="CargoPilot Resolution Verification Engine",
        action=f"EXCEPTION_{verification.verification_status}",
        entity_type="RESOLUTION_VERIFICATION",
        entity_id=verification.verification_id,
        shipment_id=verification.shipment_id,
        workflow_id=verification.workflow_id,
        run_id=verification.run_id,
        details={
            "exception_id": verification.exception_id,
            "verification_status": verification.verification_status,
            "evidence_summary": verification.evidence_summary
        }
    )

    db.add(audit)


# ==========================================================
# MAIN: VERIFY EXCEPTION RESOLUTION
# ==========================================================

def verify_exception_resolution(
    db: Session,
    exception_id: int,
    triggered_by: int = None,
    commit: bool = True
):

    try:

        # --------------------------------------------------
        # 1. GET EXCEPTION
        # --------------------------------------------------

        exception = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.exception_id == exception_id
            )
            .with_for_update()
            .first()
        )

        if exception is None:

            raise ValueError(
                f"Exception {exception_id} was not found."
            )

        if exception.status in ["RESOLVED", "CLOSED"]:

            return {
                "success": False,
                "message": (
                    "This exception is already resolved or closed."
                ),
                "exception_id": exception_id,
                "verification_status": "INCONCLUSIVE"
            }

        # --------------------------------------------------
        # 2. GET SHIPMENT
        # --------------------------------------------------

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == exception.shipment_id
            )
            .first()
        )

        if shipment is None:

            raise ValueError(
                "The shipment associated with this exception "
                "was not found."
            )

        # --------------------------------------------------
        # 3. CREATE VERIFICATION WORKFLOW
        # --------------------------------------------------

        workflow = create_verification_workflow(
            db,
            exception,
            triggered_by
        )

        # --------------------------------------------------
        # 4. CREATE VERIFICATION AGENT RUN
        # --------------------------------------------------

        run = create_verification_run(
            db,
            workflow,
            exception
        )

        # --------------------------------------------------
        # 5. VERIFY EVIDENCE
        # --------------------------------------------------

        if exception.exception_type == "DOCUMENT_MISMATCH":

            result = verify_document_mismatch(
                db,
                exception,
                shipment
            )

        elif exception.exception_type == "SHIPMENT_DELAY":

            result = verify_shipment_delay(
                db,
                exception,
                shipment
            )
        elif exception.exception_type == "MISSING_DOCUMENT":
            result = verify_missing_document(
        db,
        exception,
        shipment
    )
        else:

            result = {
                "status": "INCONCLUSIVE",
                "summary": (
                    f"Automatic verification is not yet "
                    f"implemented for {exception.exception_type}."
                ),
                "validation_results": []
            }

        verification_status = result["status"]

        # --------------------------------------------------
        # 6. SAVE VERIFICATION RECORD
        # --------------------------------------------------

        verification = ResolutionVerification(
            exception_id=exception.exception_id,
            shipment_id=shipment.shipment_id,
            workflow_id=workflow.workflow_id,
            run_id=run.run_id,
            verification_status=verification_status,
            evidence_summary=result["summary"],
            validation_results=result["validation_results"]
        )

        db.add(verification)

        db.flush()

        # --------------------------------------------------
        # 7. RESOLVE ONLY IF VERIFIED
        # --------------------------------------------------

        if verification_status == "VERIFIED":

            resolve_exception(
                db,
                exception.exception_id,
                resolution_notes=(
                    "Resolution verified by CargoPilot. "
                    + result["summary"]
                ),
                verified=True,
                commit=False
            )

        # --------------------------------------------------
        # 8. COMPLETE AGENT RUN
        # --------------------------------------------------

        run.output_data = {
            "verification_id": verification.verification_id,
            "verification_status": verification_status,
            "evidence_summary": result["summary"],
            "verification_details": result
        }

        run.execution_status = "COMPLETED"

        run.completed_at = datetime.now()

        # --------------------------------------------------
        # 9. COMPLETE WORKFLOW
        # --------------------------------------------------

        workflow.status = "COMPLETED"

        workflow.current_node = (
            f"RESOLUTION_{verification_status}"
        )

        workflow.completed_at = datetime.now()

        # --------------------------------------------------
        # 10. CREATE AUDIT LOG
        # --------------------------------------------------

        create_verification_audit_log(
            db,
            verification
        )

        # --------------------------------------------------
        # 11. COMMIT
        # --------------------------------------------------

        if commit:

            db.commit()

            db.refresh(verification)

        else:

            db.flush()

        # --------------------------------------------------
        # 12. RETURN RESULT
        # --------------------------------------------------

        return {
            "success": True,
            "message": "Resolution verification completed.",
            "exception_id": exception.exception_id,
            "shipment_id": shipment.shipment_id,
            "workflow_id": workflow.workflow_id,
            "run_id": run.run_id,
            "verification_id": verification.verification_id,
            "verification_status": verification_status,
            "evidence_summary": result["summary"],
            "exception_status": exception.status,
            "validation_results": result["validation_results"]
        }

    except Exception:

        db.rollback()

        raise
