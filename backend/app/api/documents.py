
import hashlib
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status
)
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Document, Shipment
from app.auth.dependencies import require_roles
from app.engines.document_processing import process_document


router = APIRouter(
    prefix="/api/shipments",
    tags=["Documents"]
)


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DOCUMENT_STORAGE = (
    PROJECT_ROOT / "data" / "documents"
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_DOCUMENT_TYPES = {
    "COMMERCIAL_INVOICE",
    "PACKING_LIST",
    "BILL_OF_LADING",
    "OTHER"
}


# ==================================================
# GET DOCUMENTS FOR A SHIPMENT
# ==================================================

@router.get("/{shipment_id}/documents")
def get_shipment_documents(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    documents = db.query(Document).filter(
        Document.shipment_id == shipment_id
    ).order_by(
        Document.document_id.asc()
    ).all()

    return [
        {
            "document_id": document.document_id,
            "shipment_id": document.shipment_id,
            "document_type": document.document_type,
            "file_name": document.file_name,
            "file_hash": document.file_hash,
            "extracted_fields": document.extracted_fields,
            "extraction_status": document.extraction_status,
            "validation_status": document.validation_status,
            "version_no": document.version_no,
            "uploaded_by": document.uploaded_by,
            "upload_date": document.upload_date
        }
        for document in documents
    ]


# ==================================================
# UPLOAD DOCUMENT
# ==================================================

@router.post("/{shipment_id}/documents/upload")
async def upload_document(
    shipment_id: int,

    document_type: str = Form(...),

    file: UploadFile = File(...),

    db: Session = Depends(get_db),

    current_user=Depends(
        require_roles("ADMIN", "MANAGER", "OFFICER")
    )
):

    saved_file_path = None

    try:

        # ------------------------------------------
        # STEP 1: VALIDATE DOCUMENT TYPE
        # ------------------------------------------

        document_type = document_type.upper().strip()

        if document_type not in ALLOWED_DOCUMENT_TYPES:

            raise HTTPException(
                status_code=400,
                detail="Unsupported document type."
            )

        # ------------------------------------------
        # STEP 2: CHECK SHIPMENT
        # ------------------------------------------

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == shipment_id
            )
            .with_for_update()
            .first()
        )

        if not shipment:

            raise HTTPException(
                status_code=404,
                detail="Shipment not found."
            )

        # ------------------------------------------
        # STEP 3: VALIDATE FILE NAME AND EXTENSION
        # ------------------------------------------

        if not file.filename:

            raise HTTPException(
                status_code=400,
                detail="File name is missing."
            )

        original_file_name = Path(
            file.filename.replace("\\", "/")
        ).name

        if Path(original_file_name).suffix.lower() != ".pdf":

            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed."
            )

        # ------------------------------------------
        # STEP 4: READ AND VALIDATE PDF
        # ------------------------------------------

        file_contents = await file.read(
            MAX_FILE_SIZE + 1
        )

        if not file_contents:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty."
            )

        if len(file_contents) > MAX_FILE_SIZE:

            raise HTTPException(
                status_code=413,
                detail="Maximum file size is 10 MB."
            )

        if not file_contents.startswith(b"%PDF-"):

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is not a valid PDF."
            )

        # ------------------------------------------
        # STEP 5: CALCULATE SHA-256 HASH
        # ------------------------------------------

        file_hash = hashlib.sha256(
            file_contents
        ).hexdigest()

        # ------------------------------------------
        # STEP 6: CHECK FOR DUPLICATE DOCUMENT
        # ------------------------------------------

        duplicate = db.query(Document).filter(
            Document.shipment_id == shipment_id,
            Document.document_type == document_type,
            Document.file_hash == file_hash
        ).first()

        if duplicate:

            raise HTTPException(
                status_code=409,
                detail=(
                    "This exact document has already "
                    "been uploaded for this shipment."
                )
            )

        # ------------------------------------------
        # STEP 7: ASSIGN DOCUMENT VERSION
        # ------------------------------------------

        latest_document = (
            db.query(Document)
            .filter(
                Document.shipment_id == shipment_id,
                Document.document_type == document_type
            )
            .order_by(
                Document.version_no.desc()
            )
            .first()
        )

        version_no = (
            latest_document.version_no + 1
            if latest_document
            else 1
        )

        # ------------------------------------------
        # STEP 8: CREATE STORAGE DIRECTORY
        # ------------------------------------------

        shipment_directory = (
            DOCUMENT_STORAGE / shipment.shipment_ref
        )

        shipment_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        # Use a server-generated name.
        safe_document_name = (
            document_type.lower() + f"_v{version_no}.pdf"
        )

        saved_file_path = (
            shipment_directory / safe_document_name
        )

        # Exclusive creation prevents overwriting.
        with saved_file_path.open("xb") as destination:

            destination.write(file_contents)

        # ------------------------------------------
        # STEP 9: CREATE DATABASE RECORD
        # ------------------------------------------

        new_document = Document(
            shipment_id=shipment_id,
            document_type=document_type,
            file_name=original_file_name,
            file_path=str(saved_file_path.resolve()),
            file_hash=file_hash,
            extraction_status="PENDING",
            validation_status="NOT_VALIDATED",
            version_no=version_no,
            uploaded_by=current_user.user_id
        )

        db.add(new_document)

        db.commit()

        db.refresh(new_document)

        document_id = new_document.document_id

        # ------------------------------------------
        # STEP 10: PROCESS UPLOADED DOCUMENT
        # ------------------------------------------

        try:

            processing_result = process_document(
                db,
                document_id
            )

        except Exception as processing_error:

            # Keep the uploaded document record,
            # but mark its extraction as failed.

            db.rollback()

            failed_document = db.query(Document).filter(
                Document.document_id == document_id
            ).first()

            if failed_document:

                failed_document.extraction_status = "FAILED"

                db.commit()

            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Document uploaded, but extraction failed.",
                    "document_id": document_id,
                    "error": str(processing_error)
                }
            )

        # ------------------------------------------
        # STEP 11: RETURN RESULT
        # ------------------------------------------

        return {
            "message": "Document uploaded and processed successfully.",
            "document_id": document_id,
            "shipment_id": shipment_id,
            "shipment_ref": shipment.shipment_ref,
            "document_type": document_type,
            "file_name": original_file_name,
            "version_no": version_no,
            "file_hash": file_hash,
            "extraction_status": processing_result[
                "extraction_status"
            ],
            "fields_found": processing_result[
                "fields_found"
            ],
            "extracted_fields": processing_result[
                "extracted_fields"
            ]
        }

    except HTTPException:

        db.rollback()

        # Remove an uploaded file if its database
        # record was never successfully committed.

        if saved_file_path and saved_file_path.exists():

            db_record = db.query(Document).filter(
                Document.file_path == str(
                    saved_file_path.resolve()
                )
            ).first()

            if not db_record:

                saved_file_path.unlink(
                    missing_ok=True
                )

        raise

    except Exception:

        db.rollback()

        if saved_file_path and saved_file_path.exists():

            db_record = db.query(Document).filter(
                Document.file_path == str(
                    saved_file_path.resolve()
                )
            ).first()

            if not db_record:

                saved_file_path.unlink(
                    missing_ok=True
                )

        raise

    finally:

        await file.close()
