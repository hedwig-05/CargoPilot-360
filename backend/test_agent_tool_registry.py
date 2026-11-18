import pytest

from app.agents.tool_registry import (
    execute_registered_tool,
    get_tool_catalog,
    parse_tool_selection,
)


def test_tool_catalog_contains_only_read_only_data_tools():
    catalog = get_tool_catalog()

    assert {
        item["name"] for item in catalog
    } == {
        "get_shipment_event_timeline",
        "get_document_validation_summary",
        "get_current_document_status",
    }


def test_unknown_tool_is_rejected_before_database_access():
    with pytest.raises(ValueError, match="not registered"):
        execute_registered_tool(
            db=None,
            tool_name="delete_shipment",
            shipment_id=1,
        )


def test_tool_selection_accepts_registered_tool():
    result = parse_tool_selection(
        '{"tool_name": "get_shipment_event_timeline", '
        '"rationale": "The exception concerns an overdue milestone."}'
    )

    assert result["tool_name"] == "get_shipment_event_timeline"


def test_tool_selection_accepts_no_tool():
    result = parse_tool_selection(
        '{"tool_name": "none", "rationale": "The current evidence is sufficient."}'
    )

    assert result["tool_name"] == "none"


def test_tool_selection_rejects_unregistered_tool():
    with pytest.raises(ValueError, match="unapproved tool"):
        parse_tool_selection(
            '{"tool_name": "execute_payment", "rationale": "Do it."}'
        )


def test_tool_selection_rejects_non_json_response():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_tool_selection("I think we should inspect the shipment.")
