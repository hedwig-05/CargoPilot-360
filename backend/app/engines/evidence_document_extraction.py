import re
from datetime import datetime


# Conservative rules for unstructured supporting documents.
# A subtype is assigned only when one document family has a clear,
# unique match. "OTHER" by itself is never treated as evidence.
SUBTYPE_RULES = {
    "INSPECTION_REPORT": (
        r"\binspection\s+report\b",
        r"\bcargo\s+inspection\b",
        r"\bcondition\s+inspection\b",
    ),
    "TALLY_REPORT": (
        r"\btally\s+report\b",
        r"\bcargo\s+tally\b",
        r"\bpackage\s+tally\b",
        r"\bcounting\s+report\b",
    ),
    "DAMAGE_SURVEY": (
        r"\bdamage\s+survey\b",
        r"\bsurvey\s+report\b",
        r"\bcargo\s+damage\s+assessment\b",
    ),
    "DELIVERY_RECEIPT": (
        r"\bdelivery\s+receipt\b",
        r"\bproof\s+of\s+delivery\b",
        r"\bpod\b",
        r"\bgoods\s+received\s+note\b",
    ),
    "SHORTAGE_REPORT": (
        r"\bshortage\s+report\b",
        r"\bshort[- ]landed\s+report\b",
        r"\bmissing\s+packages?\s+report\b",
    ),
    "CLAIM_SETTLEMENT": (
        r"\bclaim\s+(?:settlement|approval|accepted|approved)\b",
        r"\bsettlement\s+advice\b",
        r"\bclaim\s+outcome\b",
    ),
    "CREDIT_NOTE": (
        r"\bcredit\s+note\b",
        r"\bcredit\s+memo\b",
    ),
}

# Completeness requirements are deliberately subtype-specific. These
# scores measure extracted-field coverage, not OCR confidence or truth.
REQUIRED_FIELDS = {
    "INSPECTION_REPORT": ("shipment_ref", "document_date", "inspection_finding"),
    "TALLY_REPORT": ("shipment_ref", "document_date", "received_quantity"),
    "DAMAGE_SURVEY": ("shipment_ref", "document_date", "damage_finding"),
    "DELIVERY_RECEIPT": ("shipment_ref", "document_date", "received_quantity"),
    "SHORTAGE_REPORT": ("shipment_ref", "document_date", "received_quantity"),
    "CLAIM_SETTLEMENT": ("shipment_ref", "document_date", "claim_status"),
    "CREDIT_NOTE": ("shipment_ref", "document_date", "credit_amount"),
}

FIELD_PATTERNS = {
    "shipment_ref": (
        r"\bshipment\s*(?:reference|ref|number|no\.?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]+)",
        r"\bbooking\s*(?:reference|ref|number|no\.?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]+)",
    ),
    "container_no": (
        r"\bcontainer\s*(?:number|no\.?)\s*[:#-]?\s*([A-Z]{4}\s?\d{6,7})\b",
    ),
    "document_date": (
        r"\b(?:document\s+date|report\s+date|inspection\s+date|survey\s+date|delivery\s+date|settlement\s+date|date)\s*[:#-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"\b(?:document\s+date|report\s+date|inspection\s+date|survey\s+date|delivery\s+date|settlement\s+date|date)\s*[:#-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
    ),
    "expected_quantity": (
        r"\b(?:expected|manifested|declared)\s+(?:quantity|packages?|cartons?)\s*[:#-]?\s*(\d+)",
    ),
    "received_quantity": (
        r"\b(?:final\s+)?(?:actual\s+)?(?:received|counted|delivered)\s+(?:quantity|packages?|cartons?)\s*[:#-]?\s*(\d+)",
        r"\bpackages?\s+received\s*[:#-]?\s*(\d+)",
    ),
    "damaged_quantity": (
        r"\b(?:damaged|affected)\s+(?:quantity|packages?|cartons?)\s*[:#-]?\s*(\d+)",
    ),
    "claim_status": (
        r"\bclaim\s+status\s*[:#-]?\s*(accepted|approved|settled|rejected|denied|pending)",
        r"\b(outcome|decision)\s*[:#-]?\s*(accepted|approved|settled|rejected|denied|pending)",
    ),
    "credit_amount": (
        r"\b(?:credit\s+amount|total\s+credit|credit\s+note\s+total)\s*[:#-]?\s*([A-Z]{3}\s*)?([0-9,]+(?:\.\d{2})?)",
    ),
    "inspection_finding": (
        r"\b(?:inspection\s+finding|findings?|condition)\s*[:#-]?\s*(.{3,160})",
    ),
    "damage_finding": (
        r"\b(?:damage\s+finding|damage\s+description|damage\s+observed)\s*[:#-]?\s*(.{3,160})",
    ),
}


def _normalise_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if match.lastindex and match.lastindex > 1:
                return " ".join(part for part in match.groups() if part).strip()
            return match.group(1).strip()
    return None


def classify_other_document(extracted_text):
    """
    Return a conservative subtype and evidence-role classification.

    Unknown or ambiguous documents remain unclassified. The returned
    classification confidence is separate from extraction completeness.
    """
    text = _normalise_text(extracted_text)
    scores = {}

    for subtype, patterns in SUBTYPE_RULES.items():
        hits = sum(bool(re.search(pattern, text, re.IGNORECASE)) for pattern in patterns)
        if hits:
            scores[subtype] = hits

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    subtype = None
    classification_confidence = 0.0

    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        subtype = ranked[0][0]
        classification_confidence = min(1.0, 0.70 + 0.10 * (ranked[0][1] - 1))

    role = None
    if subtype in {"INSPECTION_REPORT", "DAMAGE_SURVEY", "SHORTAGE_REPORT"}:
        role = "INCIDENT_EVIDENCE"
    elif subtype in {"CLAIM_SETTLEMENT", "CREDIT_NOTE"}:
        role = "RESOLUTION_EVIDENCE"
    elif subtype == "DELIVERY_RECEIPT":
        if re.search(r"\b(?:replacement|re-delivery|redelivery)\b", text, re.IGNORECASE):
            role = "RESOLUTION_EVIDENCE"
    elif subtype == "TALLY_REPORT":
        if re.search(r"\b(?:final|corrected|revised|replacement)\s+(?:tally|count)\b", text, re.IGNORECASE):
            role = "RESOLUTION_EVIDENCE"
        elif re.search(r"\b(?:initial|first|arrival)\s+(?:tally|count)\b", text, re.IGNORECASE):
            role = "INCIDENT_EVIDENCE"

    return {
        "document_subtype": subtype,
        "evidence_role": role,
        "classification_confidence": round(classification_confidence, 4),
    }


def extract_other_document_fields(extracted_text):
    """Extract supported evidence fields and a completeness score (0..1)."""
    text = _normalise_text(extracted_text)
    classification = classify_other_document(extracted_text)
    fields = {}

    for field_name, patterns in FIELD_PATTERNS.items():
        value = _first_match(patterns, text)
        if value:
            fields[field_name] = value

    subtype = classification["document_subtype"]
    required = REQUIRED_FIELDS.get(subtype, ())
    completeness = (
        sum(field in fields for field in required) / len(required)
        if required else 0.0
    )

    return {
        **classification,
        "extracted_fields": fields,
        "fields_found": len(fields),
        "extraction_confidence": round(completeness, 4),
        "confidence_basis": "REQUIRED_FIELD_COMPLETENESS",
    }
