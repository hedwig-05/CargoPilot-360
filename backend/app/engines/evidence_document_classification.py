"""Deterministic classification for non-standard logistics evidence documents.

This module deliberately does not infer a subtype from the generic document_type
value OTHER. It uses explicit textual signals and leaves ambiguous documents
unclassified so they cannot be used for automatic resolution verification.
"""

import re
from typing import Optional


SUBTYPE_PATTERNS = (
    ("CLAIM_SETTLEMENT", (
        r"\\bCLAIM\\s+SETTLEMENT\\b",
        r"\\bSETTLEMENT\\s+ADVICE\\b",
        r"\\bCLAIM\\s+APPROVAL\\b",
    )),
    ("CREDIT_NOTE", (
        r"\\bCREDIT\\s+NOTE\\b",
    )),
    ("DAMAGE_SURVEY", (
        r"\\bDAMAGE\\s+SURVEY\\b",
        r"\\bCARGO\\s+DAMAGE\\s+SURVEY\\b",
        r"\\bSURVEYOR(?:'S)?\\s+REPORT\\b",
    )),
    ("INSPECTION_REPORT", (
        r"\\bINSPECTION\\s+REPORT\\b",
        r"\\bCARGO\\s+INSPECTION\\b",
        r"\\bCONDITION\\s+REPORT\\b",
    )),
    ("SHORTAGE_REPORT", (
        r"\\bSHORTAGE\\s+REPORT\\b",
        r"\\bCARGO\\s+SHORTAGE\\s+REPORT\\b",
    )),
    ("DELIVERY_RECEIPT", (
        r"\\bDELIVERY\\s+RECEIPT\\b",
        r"\\bPROOF\\s+OF\\s+DELIVERY\\b",
        r"\\bPOD\\b",
    )),
    ("TALLY_REPORT", (
        r"\\bTALLY\\s+(?:SHEET|REPORT|RECORD)\\b",
        r"\\bCARGO\\s+TALLY\\b",
        r"\\bDISCHARGE\\s+TALLY\\b",
    )),
)


def _normalise_text(text: str) -> str:
    """Normalise whitespace while preserving words and punctuation."""
    return re.sub(r"\\s+", " ", (text or "")).strip().upper()


def _matching_subtypes(text: str) -> list[str]:
    matches = []
    for subtype, patterns in SUBTYPE_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            matches.append(subtype)
    return matches


def _classify_tally_role(text: str) -> Optional[str]:
    """Only classify tally role when the report states its purpose clearly."""
    incident_signals = (
        r"\\bINITIAL\\s+TALLY\\b",
        r"\\bSHORT\\s*LANDED\\b",
        r"\\bSHORTAGE\\b",
        r"\\bLESS\\s+THAN\\s+EXPECTED\\b",
        r"\\bDAMAGED\\s+PACKAGES?\\b",
    )
    resolution_signals = (
        r"\\bFINAL\\s+TALLY\\b",
        r"\\bRECOUNT\\b",
        r"\\bCORRECTED\\s+TALLY\\b",
        r"\\bADDITIONAL\\s+(?:CARGO|PACKAGES?)\\s+RECEIVED\\b",
        r"\\bSHORTAGE\\s+MADE\\s+GOOD\\b",
    )

    incident = any(re.search(pattern, text) for pattern in incident_signals)
    resolution = any(re.search(pattern, text) for pattern in resolution_signals)

    if incident == resolution:
        return None
    return "INCIDENT_EVIDENCE" if incident else "RESOLUTION_EVIDENCE"


def classify_evidence_document(extracted_text: str) -> dict:
    """Return a conservative subtype and evidence-role classification.

    Classification confidence is a rule-match score, not OCR confidence and
    not proof that the document's statements are true. A caller must keep
    documents with missing subtype or role out of automatic verification.
    """
    text = _normalise_text(extracted_text)
    matches = _matching_subtypes(text)

    if len(matches) != 1:
        return {
            "document_subtype": None,
            "evidence_role": None,
            "classification_confidence": 0.0,
            "classification_reason": (
                "No recognised subtype found."
                if not matches
                else "Conflicting subtype signals found."
            ),
        }

    subtype = matches[0]
    role = None

    if subtype in {"INSPECTION_REPORT", "DAMAGE_SURVEY", "SHORTAGE_REPORT"}:
        role = "INCIDENT_EVIDENCE"
    elif subtype in {"CLAIM_SETTLEMENT", "CREDIT_NOTE"}:
        role = "RESOLUTION_EVIDENCE"
    elif subtype == "TALLY_REPORT":
        role = _classify_tally_role(text)
    elif subtype == "DELIVERY_RECEIPT":
        # A generic delivery receipt is not necessarily a replacement receipt.
        if re.search(
            r"\\b(REPLACEMENT|REPLACED|SHORTAGE\\s+MADE\\s+GOOD)\\b",
            text,
        ):
            role = "RESOLUTION_EVIDENCE"

    if role is None:
        return {
            "document_subtype": subtype,
            "evidence_role": None,
            "classification_confidence": 0.75,
            "classification_reason": (
                "Subtype recognised, but evidence role is ambiguous."
            ),
        }

    return {
        "document_subtype": subtype,
        "evidence_role": role,
        "classification_confidence": 0.95,
        "classification_reason": "Subtype and evidence role matched explicit text signals.",
    }
