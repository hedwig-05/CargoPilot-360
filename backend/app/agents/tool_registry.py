import json
import re

from app.models import Document, DocumentValidation, ShipmentEvent


TOOL_CATALOG = [
    {
        "name": "get_shipment_event_timeline",
        "description": (
            "Read the shipment's recorded milestone timeline, including "
            "expected and actual times and event status."
        ),
        "use_when": (
            "The exception may be related to a delayed, missing or "
            "inconsistent shipment milestone."
        ),
    },
    {
        "name": "get_document_validation_summary",
        "description": (
            "Read recent document validation outcomes by field and document "
            "type. Raw extracted and expected values are not exposed."
        ),
        "use_when": (
            "The exception may involve a document mismatch, missing field "
            "or uncertain validation result."
        ),
    },
    {
        "name": "get_current_document_status",
        "description": (
            "Read the latest version and extraction/validation status for "
            "each document type attached to the shipment."
        ),
        "use_when": (
            "The exception may involve missing, unprocessed, outdated or "
            "incompletely validated documents."
        ),
    },
]


def get_shipment_event_timeline(db, shipment_id):
    events = (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment_id)
        .order_by(
            ShipmentEvent.expected_time.asc(),
            ShipmentEvent.event_id.asc()
        )
        .limit(30)
        .all()
    )

    return {
        "shipment_id": shipment_id,
        "event_count": len(events),
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "event_description": event.event_description,
                "expected_time": (
                    event.expected_time.isoformat()
                    if event.expected_time else None
                ),
                "actual_time": (
                    event.actual_time.isoformat()
                    if event.actual_time else None
                ),
                "event_status": event.event_status,
            }
            for event in events
        ],
    }


def get_document_validation_summary(db, shipment_id):
    validations = (
        db.query(DocumentValidation, Document.document_type)
        .join(
            Document,
            Document.document_id == DocumentValidation.document_id
        )
        .filter(DocumentValidation.shipment_id == shipment_id)
        .order_by(
            DocumentValidation.validated_at.desc(),
            DocumentValidation.validation_id.desc()
        )
        .limit(50)
        .all()
    )

    return {
        "shipment_id": shipment_id,
        "validation_count": len(validations),
        "validations": [
            {
                "validation_id": validation.validation_id,
                "document_type": document_type,
                "field_name": validation.field_name,
                "result": validation.validation_result,
                "explanation": validation.explanation,
                "validated_at": (
                    validation.validated_at.isoformat()
                    if validation.validated_at else None
                ),
            }
            for validation, document_type in validations
        ],
    }


def get_current_document_status(db, shipment_id):
    documents = (
        db.query(Document)
        .filter(Document.shipment_id == shipment_id)
        .order_by(
            Document.document_type.asc(),
            Document.version_no.desc(),
            Document.upload_date.desc(),
            Document.document_id.desc()
        )
        .all()
    )

    latest_by_type = {}
    for document in documents:
        if document.document_type not in latest_by_type:
            latest_by_type[document.document_type] = document

    latest_documents = list(latest_by_type.values())

    return {
        "shipment_id": shipment_id,
        "document_count": len(latest_documents),
        "documents": [
            {
                "document_id": document.document_id,
                "document_type": document.document_type,
                "version_no": document.version_no,
                "extraction_status": document.extraction_status,
                "validation_status": document.validation_status,
                "extraction_confidence": (
                    float(document.extraction_confidence)
                    if document.extraction_confidence is not None
                    else None
                ),
            }
            for document in latest_documents
        ],
    }


TOOL_HANDLERS = {
    "get_shipment_event_timeline": get_shipment_event_timeline,
    "get_document_validation_summary": get_document_validation_summary,
    "get_current_document_status": get_current_document_status,
}


def get_tool_catalog():
    """Return descriptions only; execution remains server-controlled."""
    return list(TOOL_CATALOG)


def execute_registered_tool(db, tool_name, shipment_id):
    """
    Execute one allowlisted, read-only tool.

    The caller supplies shipment_id from trusted graph state. The LLM
    is never allowed to supply database identifiers or arbitrary arguments.
    """
    if not isinstance(tool_name, str):
        raise ValueError("Tool name must be a string.")

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        raise ValueError(f"Tool '{tool_name}' is not registered.")

    if not isinstance(shipment_id, int) or shipment_id <= 0:
        raise ValueError("A valid shipment_id is required.")

    return {
        "tool_name": tool_name,
        "read_only": True,
        "result": handler(db, shipment_id),
    }


def parse_tool_selection(response_text):
    """
    Parse the model's JSON tool choice and fail closed on invalid output.
    """
    if not isinstance(response_text, str):
        raise ValueError("Tool selection response must be text.")

    cleaned = response_text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^\`\`\`(?:json)?\s*|\s*\`\`\`$",
            "",
            cleaned,
            flags=re.IGNORECASE
        ).strip()

    try:
        selection = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("LLM did not return valid JSON tool selection.") from error

    if not isinstance(selection, dict):
        raise ValueError("Tool selection must be a JSON object.")

    tool_name = selection.get("tool_name")
    rationale = selection.get("rationale")

    if not isinstance(tool_name, str) or not isinstance(rationale, str):
        raise ValueError(
            "Tool selection must contain string tool_name and rationale."
        )

    tool_name = tool_name.strip()
    rationale = rationale.strip()

    allowed_names = set(TOOL_HANDLERS) | {"none"}
    if tool_name not in allowed_names:
        raise ValueError(
            f"LLM selected an unapproved tool: {tool_name!r}."
        )

    if not rationale:
        raise ValueError("Tool selection rationale cannot be empty.")

    return {
        "tool_name": tool_name,
        "rationale": rationale[:1000],
    }
