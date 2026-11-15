"""Manual read-only document-file existence check."""
from pathlib import Path
from app.database.connection import SessionLocal
from app.models import Document


def main():
    db = SessionLocal()
    try:
        documents = db.query(Document).order_by(Document.document_id).all()
        print("\n===== DOCUMENT FILE CHECK =====")
        for document in documents:
            file_path = Path(document.file_path)
            print(
                f"ID: {document.document_id} | "
                f"File: {document.file_name} | "
                f"Exists: {file_path.exists()}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
