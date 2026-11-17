"""Manual PDF field-extraction smoke test."""
from app.engines.document_extraction import extract_pdf_text
from app.engines.document_field_extraction import extract_document_fields

PDF_PATH = r"C:\Users\Laptop\Desktop\Cargo 360\data\documents\CP-SHP-2026-001\bill_of_lading.pdf"


def main():
    try:
        pdf_result = extract_pdf_text(PDF_PATH)
        field_result = extract_document_fields(
            pdf_result["extracted_text"], "BILL_OF_LADING"
        )
        print("\n===== STRUCTURED EXTRACTION RESULT =====")
        print("Document Type:", field_result["document_type"])
        print("Fields Found:", field_result["fields_found"])
        print("\n===== EXTRACTED FIELDS =====")
        for field, value in field_result["extracted_fields"].items():
            print(f"{field}: {value}")
    except Exception as e:
        print("ERROR:", e)
        raise


if __name__ == "__main__":
    main()
