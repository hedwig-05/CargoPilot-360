
from sqlalchemy.orm import Session

from app.models import Document

from app.engines.document_extraction import extract_pdf_text
from app.engines.document_field_extraction import extract_document_fields


def process_document(db: Session, document_id: int):
    """
    Process one document:
    1. Find document in MySQL.
    2. Extract PDF text.
    3. Extract structured fields.
    4. Save extracted information to MySQL.
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

        # Step 2: Extract structured fields
        field_result = extract_document_fields(
            pdf_result["extracted_text"],
            document.document_type
        )

        # Step 3: Save extracted information
        document.extracted_text = pdf_result["extracted_text"]

        document.extracted_fields = field_result[
            "extracted_fields"
        ]

        document.extraction_status = pdf_result[
            "extraction_status"
        ]

        # Step 4: Save changes to MySQL
        db.commit()

        return {
            "message": "Document processing completed",
            "document_id": document.document_id,
            "file_name": document.file_name,
            "extraction_status": document.extraction_status,
            "fields_found": field_result["fields_found"],
            "extracted_fields": field_result["extracted_fields"]
        }

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
                "fields_found": result["fields_found"]
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
