from app.engines.document_extraction import extract_pdf_text


pdf_path = input("Enter the PDF file path: ")

try:
    result = extract_pdf_text(pdf_path)

    print("\n===== PDF EXTRACTION RESULT =====")
    print("File:", result["file_name"])
    print("Pages:", result["total_pages"])
    print("Status:", result["extraction_status"])

    print("\n===== EXTRACTED TEXT =====")
    print(result["extracted_text"])

except Exception as e:
    print("ERROR:", e)
