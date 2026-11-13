
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentValidation,
    Shipment,
    Exception as ShipmentException
)


# ==========================================================
# FIELD DEFINITIONS
# ==========================================================

# Fields that should appear in both documents
SHARED_FIELDS = [
    "shipment_ref",
    "container_no",
    "shipper",
    "consignee",
    "cargo_description"
]


# Fields that can be checked against the shipment database
SHIPMENT_FIELDS = [
    "shipment_ref",
    "container_no",
    "shipper",
    "consignee"
]


# ==========================================================
# NORMALIZE VALUES
# ==========================================================

def normalize_value(value):
    """Normalize values before comparing them."""

    if value is None:
        return None

    return " ".join(
        str(value).strip().lower().split()
    )


# ==========================================================
# COMPARE VALUES
# ==========================================================

def compare_values(value1, value2):
    """Compare two values and return a validation result."""

    normalized1 = normalize_value(value1)
    normalized2 = normalize_value(value2)

    if not normalized1 and not normalized2:
        return "MISSING"

    if not normalized1 or not normalized2:
        return "MISSING"

    if normalized1 == normalized2:
        return "MATCH"

    return "MISMATCH"


# ==========================================================
# SAVE VALIDATION
# ==========================================================

def save_validation(
    db,
    document_id,
    compared_document_id,
    shipment_id,
    field_name,
    extracted_value,
    expected_value,
    result,
    explanation
):
    """
    Insert or update a validation record.

    This prevents duplicate records when the engine is run again.
    """

    query = db.query(DocumentValidation).filter(
        DocumentValidation.document_id == document_id,
        DocumentValidation.shipment_id == shipment_id,
        DocumentValidation.field_name == field_name
    )

    if compared_document_id is None:

        query = query.filter(
            DocumentValidation.compared_document_id.is_(None)
        )

    else:

        query = query.filter(
            DocumentValidation.compared_document_id
            == compared_document_id
        )

    validation = query.first()

    if validation is None:

        validation = DocumentValidation(
            document_id=document_id,
            compared_document_id=compared_document_id,
            shipment_id=shipment_id,
            field_name=field_name
        )

        db.add(validation)

    validation.extracted_value = (
        str(extracted_value)[:255]
        if extracted_value is not None else None
    )

    validation.expected_value = (
        str(expected_value)[:255]
        if expected_value is not None else None
    )

    validation.validation_result = result
    validation.explanation = explanation

    # Refresh the timestamp whenever validation is performed.
    validation.validated_at = func.now()

    return validation


# ==========================================================
# CREATE MISMATCH EXCEPTION
# ==========================================================

def create_mismatch_exception(
    db,
    shipment_id,
    description,
    document_id=None
):
    """Create an exception if no active mismatch exception exists."""

    existing = db.query(ShipmentException).filter(
        ShipmentException.shipment_id == shipment_id,
        ShipmentException.exception_type == "DOCUMENT_MISMATCH",
        ShipmentException.status.notin_(
            ["RESOLVED", "CLOSED"]
        )
    ).first()

    if existing:
        return False

    exception = ShipmentException(
        shipment_id=shipment_id,
        document_id=document_id,
        exception_type="DOCUMENT_MISMATCH",
        description=description,
        severity="HIGH",
        status="OPEN",
        detected_by="DOCUMENT_VALIDATION_ENGINE"
    )

    db.add(exception)

    return True


# ==========================================================
# VALIDATE SHIPMENT DOCUMENTS
# ==========================================================

def validate_shipment_documents(
    db: Session,
    shipment_id: int,
    commit: bool = True
):
    """
    Validate the Commercial Invoice and Bill of Lading.

    Comparisons:
    1. Invoice against Bill of Lading.
    2. Each document against the shipment database.

    Set commit=False to test without permanently saving results.
    """

    try:

        # --------------------------------------------------
        # 1. GET SHIPMENT
        # --------------------------------------------------

        shipment = db.query(Shipment).filter(
            Shipment.shipment_id == shipment_id
        ).first()

        if not shipment:

            raise ValueError(
                f"Shipment ID {shipment_id} not found."
            )

        # --------------------------------------------------
        # 2. GET REQUIRED DOCUMENTS
        # --------------------------------------------------

        documents = (
            db.query(Document)
            .filter(
                Document.shipment_id == shipment_id,
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

        invoice = next(
            (
                doc for doc in documents
                if doc.document_type == "COMMERCIAL_INVOICE"
            ),
            None
        )

        bill_of_lading = next(
            (
                doc for doc in documents
                if doc.document_type == "BILL_OF_LADING"
            ),
            None
        )

        if not invoice or not bill_of_lading:

            raise ValueError(
                "Both Commercial Invoice and Bill of Lading "
                "are required for document comparison."
            )

        if (
            invoice.extraction_status != "EXTRACTED"
            or bill_of_lading.extraction_status != "EXTRACTED"
        ):

            raise ValueError(
                "Both documents must be successfully extracted first."
            )

        invoice_fields = invoice.extracted_fields or {}
        bol_fields = bill_of_lading.extracted_fields or {}

        validations = []
        mismatch_details = []

        document_results = {
            invoice.document_id: [],
            bill_of_lading.document_id: []
        }

        # --------------------------------------------------
        # 3. COMPARE INVOICE AGAINST BILL OF LADING
        # --------------------------------------------------

        for field in SHARED_FIELDS:

            invoice_value = invoice_fields.get(field)
            bol_value = bol_fields.get(field)

            # Ignore fields missing from both documents.
            if (
                normalize_value(invoice_value) is None
                and normalize_value(bol_value) is None
            ):
                continue

            result = compare_values(
                invoice_value,
                bol_value
            )

            explanation = (
                f"Comparison of {field} between "
                "Commercial Invoice and Bill of Lading."
            )

            # Save result for the invoice.
            save_validation(
                db,
                invoice.document_id,
                bill_of_lading.document_id,
                shipment_id,
                field,
                invoice_value,
                bol_value,
                result,
                explanation
            )

            # Save reverse result for the BOL.
            save_validation(
                db,
                bill_of_lading.document_id,
                invoice.document_id,
                shipment_id,
                field,
                bol_value,
                invoice_value,
                result,
                explanation
            )

            document_results[invoice.document_id].append(result)
            document_results[bill_of_lading.document_id].append(result)

            validations.append({
                "comparison": "INVOICE_VS_BOL",
                "field": field,
                "result": result
            })

            if result == "MISMATCH":

                mismatch_details.append({
                    "field": field,
                    "invoice_document_id": invoice.document_id,
                    "bol_document_id": bill_of_lading.document_id,
                    "invoice_value": invoice_value,
                    "bol_value": bol_value
                })

        # --------------------------------------------------
        # 4. COMPARE EACH DOCUMENT AGAINST SHIPMENT RECORDS
        # --------------------------------------------------

        shipment_fields = {
            "shipment_ref": shipment.shipment_ref,
            "container_no": shipment.container_no,
            "shipper": shipment.shipper,
            "consignee": shipment.consignee
        }

        for document in [invoice, bill_of_lading]:

            extracted_fields = document.extracted_fields or {}

            for field in SHIPMENT_FIELDS:

                extracted_value = extracted_fields.get(field)
                expected_value = shipment_fields[field]

                if (
                    normalize_value(extracted_value) is None
                    and normalize_value(expected_value) is None
                ):
                    continue

                result = compare_values(
                    extracted_value,
                    expected_value
                )

                explanation = (
                    f"Comparison of {field} in "
                    f"{document.document_type} against "
                    "the shipment database record."
                )

                save_validation(
                    db,
                    document.document_id,
                    None,
                    shipment_id,
                    field,
                    extracted_value,
                    expected_value,
                    result,
                    explanation
                )

                document_results[document.document_id].append(result)

                validations.append({
                    "comparison": "DOCUMENT_VS_SHIPMENT",
                    "document_id": document.document_id,
                    "field": field,
                    "result": result
                })

                if result == "MISMATCH":

                    mismatch_details.append({
                        "field": field,
                        "document_id": document.document_id,
                        "document_type": document.document_type,
                        "document_value": extracted_value,
                        "shipment_value": expected_value
                    })

        # --------------------------------------------------
        # 5. UPDATE DOCUMENT VALIDATION STATUS
        # --------------------------------------------------

        for document in [invoice, bill_of_lading]:

            results = document_results[document.document_id]

            if "MISMATCH" in results:

                document.validation_status = "MISMATCH"

            elif (
                "MISSING" in results
                or "UNCERTAIN" in results
                or not results
            ):

                document.validation_status = "INCOMPLETE"

            else:

                document.validation_status = "VALID"

        # --------------------------------------------------
        # 6. CREATE MISMATCH EXCEPTION
        # --------------------------------------------------

        exception_created = False

        if mismatch_details:

            mismatch_fields = sorted({
                item["field"]
                for item in mismatch_details
            })

            description = (
                "Document mismatches detected. "
                "Affected fields: "
                + ", ".join(mismatch_fields)
                + ". Details: "
                + "; ".join(
                    (
                        f"{item['field']}: "
                        f"Invoice={item.get('invoice_value')}, "
                        f"BOL={item.get('bol_value')}"
                    )
                    if "invoice_value" in item
                    else (
                        f"{item['field']}: "
                        f"{item.get('document_type')}="
                        f"{item.get('document_value')}, "
                        f"Shipment={item.get('shipment_value')}"
                    )
                    for item in mismatch_details
                )
            )

            # Always associate the exception with the
            # original Commercial Invoice.
            exception_document_id = invoice.document_id

            exception_created = create_mismatch_exception(
                db,
                shipment_id,
                description,
                exception_document_id
            )

        # --------------------------------------------------
        # 7. COUNT VALIDATION RESULTS
        # --------------------------------------------------

        result_counts = {
            "MATCH": 0,
            "MISMATCH": 0,
            "MISSING": 0,
            "UNCERTAIN": 0
        }

        for item in validations:

            result_counts[item["result"]] += 1

        # --------------------------------------------------
        # 8. COMMIT OR LEAVE CHANGES PENDING FOR TESTING
        # --------------------------------------------------

        if commit:

            db.commit()

        return {
            "message": "Document validation completed",
            "shipment_id": shipment_id,
            "total_validations": len(validations),
            "result_counts": result_counts,
            "mismatches": sorted({
                item["field"] for item in mismatch_details
            }),
            "exception_created": exception_created,
            "document_statuses": {
                "invoice": invoice.validation_status,
                "bill_of_lading": bill_of_lading.validation_status
            },
            "validations": validations
        }

    except Exception:

        db.rollback()
        raise
