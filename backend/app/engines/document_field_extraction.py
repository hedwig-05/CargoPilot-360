
import re


def extract_document_fields(extracted_text: str, document_type: str):
    """
    Extract structured fields from Commercial Invoice
    and Bill of Lading text.

    Supports:
    - Labels and values on the same line.
    - Labels and values on separate lines.
    - Paired SHIPPER / CONSIGNEE sections.
    - Combined section headings such as SELLER / SHIPPER.
    """

    lines = [
        line.strip()
        for line in extracted_text.splitlines()
        if line.strip()
    ]

    fields = {}

    field_patterns = {
        "shipment_ref": [
            "Shipment Reference",
            "Shipment Ref"
        ],
        "container_no": [
            "Container Number",
            "Container No"
        ],
        "shipper": [
            "Shipper",
            "Exporter",
            "Seller"
        ],
        "consignee": [
            "Consignee",
            "Importer",
            "Buyer"
        ],
        "cargo_description": [
            "Cargo Description",
            "Description of Goods",
            "Goods Description"
        ],
        "packages": [
            "Quantity / Packages",
            "Number of Packages",
            "Packages",
            "Quantity"
        ],
        "port_of_loading": [
            "Port of Loading"
        ],
        "port_of_discharge": [
            "Port of Discharge"
        ],
        "origin": [
            "Origin"
        ],
        "destination": [
            "Destination"
        ],
        "bol_number": [
            "Bill of Lading Number",
            "B/L Number",
            "BOL Number"
        ],
        "invoice_number": [
            "Invoice Number",
            "Invoice No"
        ],
        "invoice_date": [
            "Invoice Date",
            "Date of Invoice"
        ],
        "total_amount": [
            "Total Invoice Value",
            "Total Amount",
            "Invoice Total",
            "Grand Total"
        ],
        "currency": [
            "Currency"
        ]
    }

    # ------------------------------------------------
    # STEP 1: HANDLE PAIRED SHIPPER / CONSIGNEE LABELS
    # ------------------------------------------------

    for index in range(len(lines) - 3):

        if (
            lines[index].upper() == "SHIPPER"
            and lines[index + 1].upper() == "CONSIGNEE"
        ):

            fields["shipper"] = lines[index + 2]
            fields["consignee"] = lines[index + 3]

            break

    # ------------------------------------------------
    # STEP 2: BUILD A SET OF ALL KNOWN LABELS
    # ------------------------------------------------

    known_labels = {
        label.upper()
        for labels in field_patterns.values()
        for label in labels
    }

    # ------------------------------------------------
    # STEP 3: EXTRACT REMAINING FIELDS
    # ------------------------------------------------

    for field_name, labels in field_patterns.items():

        if field_name in fields:
            continue

        for index, line in enumerate(lines):

            # Ignore combined section headings.
            # These are headings, not field values.

            if re.fullmatch(
                r"SELLER\s*/\s*SHIPPER|BUYER\s*/\s*CONSIGNEE",
                line,
                re.IGNORECASE
            ):
                continue

            for label in labels:

                pattern = (
                    r"^"
                    + re.escape(label)
                    + r"\s*:?\s*(.*)$"
                )

                match = re.search(
                    pattern,
                    line,
                    re.IGNORECASE
                )

                if not match:
                    continue

                value = match.group(1).strip()

                # Reject section-heading fragments such as
                # "/ SHIPPER" and "/ CONSIGNEE".

                if value.startswith("/"):
                    continue

                # If the value is on the next line,
                # make sure that line is not another label.

                if not value and index + 1 < len(lines):

                    next_line = lines[index + 1].strip()

                    if next_line.upper() not in known_labels:
                        value = next_line

                if value:
                    fields[field_name] = value
                    break

            if field_name in fields:
                break

    return {
        "document_type": document_type,
        "extracted_fields": fields,
        "fields_found": len(fields)
    }
