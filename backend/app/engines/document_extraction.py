from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(file_path: str):
    """
    Extract text from a PDF document.
    """

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF documents are supported.")

    reader = PdfReader(str(pdf_path))

    extracted_text = []

    for page_number, page in enumerate(reader.pages, start=1):

        page_text = page.extract_text()

        if page_text:
            extracted_text.append(
                f"--- Page {page_number} ---\n{page_text}"
            )

    full_text = "\n\n".join(extracted_text)

    return {
        "file_name": pdf_path.name,
        "total_pages": len(reader.pages),
        "extracted_text": full_text,
        "extraction_status": (
            "EXTRACTED" if full_text.strip() else "NEEDS_REVIEW"
        )
    }
