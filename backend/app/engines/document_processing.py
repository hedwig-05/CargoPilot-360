from sqlalchemy.orm import Session

from app.models import Document

from app.engines.document_extraction import extract_pdf_text
from app.engines.document_field_extraction import extract_document_fields
from app.engines.evidence_document_extraction import extract_other_document_fields


def process_document(db: Session, document_id: int):
    """
    Process one document:
    1. Find the document in MySQL.
    2. Extract PDF text.
    3. Route OTHER documents through conservative evidence extraction;
       retain the existing invoice/BOL/packing-list parser otherwise.
    4. Save the extracted information and evidence classification.
    """

    document = db.query(Document).filter(
        Document.document_id == document_id
    ).first()

    if not document:
        raise ValueError(
            f"Document ID {document_id} not found."
        )

    try:
        # Step 1: Extract text from PDF
        pdf_result = extract_pdf_text(
            document.file_path
        )
        extracted_text = pdf_result["extracted_text"]

        # Step 2: Select the appropriate structured extractor
        if document.document_type == "OTHER":
            field_result = extract_other_document_fields(
                extracted_text
            )

            document.document_subtype = field_result["document_subtype"]
            document.evidence_role = field_result["evidence_role"]
            document.extraction_confidence = field_result[
                "extraction_confidence"
            ]
        else:
            # Preserve the established invoice/BOL extraction behaviour.
            field_result = extract_document_fields(
                extracted_text,
                document.document_type
            )

            document.document_subtype = None
            document.evidence_role = None
            document.extraction_confidence = None

        # Step 3: Save extracted information
        document.extracted_text = extracted_text
        document.extracted_fields = field_result["extracted_fields"]
        document.extraction_status = pdf_result["extraction_status"]

        # Step 4: Save changes to MySQL
        db.commit()

        result = {
            "message": "Document processing completed",
            "document_id": document.document_id,
            "file_name": document.file_name,
            "document_type": document.document_type,
            "extraction_status": document.extraction_status,
            "fields_found": field_result["fields_found"],
            "extracted_fields": field_result["extracted_fields"],
            "document_subtype": document.document_subtype,
            "evidence_role": document.evidence_role,
            "extraction_confidence": (
                float(document.extraction_confidence)
                if document.extraction_confidence is not None
                else None
            ),
        }

        if document.document_type == "OTHER":
            result["classification_confidence"] = field_result[
                "classification_confidence"
            ]
            result["confidence_basis"] = field_result["confidence_basis"]

        return result

    except Exception:
        db.rollback()
        raise


def process_all_documents(db: Session):
    """
    Process all documents stored in MySQL.
    """

    documents = db.query(Document).order_by(
        Document.document_id
    ).all()

    results = []

    for document in documents:

        document_id = document.document_id
        file_name = document.file_name

        try:

            result = process_document(
                db,
                document_id
            )

            results.append({
                "document_id": document_id,
                "file_name": file_name,
                "status": "SUCCESS",
                "extraction_status": result["extraction_status"],
                "fields_found": result["fields_found"],
                "document_subtype": result["document_subtype"],
                "evidence_role": result["evidence_role"],
                "extraction_confidence": result["extraction_confidence"]
            })

        except Exception as e:

            results.append({
                "document_id": document_id,
                "file_name": file_name,
                "status": "FAILED",
                "error": str(e)
            })

    successful = sum(
        1 for item in results
        if item["status"] == "SUCCESS"
    )

    failed = sum(
        1 for item in results
        if item["status"] == "FAILED"
    )

    return {
        "message": "Bulk document processing completed",
        "total_documents": len(documents),
        "successful": successful,
        "failed": failed,
        "results": results
    }
