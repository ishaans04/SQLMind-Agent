from types import SimpleNamespace

import pytest

from sqlmind_agent.mcp_client import (
    MCPClientError,
    _extract_payload,
    _normalize_results,
    _normalize_schema,
)


def test_extract_payload_from_structured_content() -> None:
    result = SimpleNamespace(structured_content={"success": True, "value": 1})

    assert _extract_payload(result) == {"success": True, "value": 1}


def test_extract_payload_from_text_content() -> None:
    result = SimpleNamespace(
        structured_content=None,
        content=[SimpleNamespace(text='{"success": true, "value": 1}')],
    )

    assert _extract_payload(result) == {"success": True, "value": 1}


def test_extract_payload_rejects_non_json_content() -> None:
    result = SimpleNamespace(structured_content=None, content=[SimpleNamespace(text="not json")])

    with pytest.raises(MCPClientError, match="non-JSON"):
        _extract_payload(result)


def test_normalize_schema_from_sqlmind_mcp_shape() -> None:
    schema = _normalize_schema(
        {
            "success": True,
            "schema": {
                "sales": [
                    {
                        "name": "amount",
                        "type": "REAL",
                        "nullable": False,
                        "primary_key": False,
                    }
                ]
            },
        }
    )

    assert schema.tables[0].name == "sales"
    assert schema.tables[0].columns[0].name == "amount"


def test_normalize_results_converts_row_lists_to_dicts() -> None:
    results = _normalize_results(
        {
            "success": True,
            "columns": ["region", "total_sales"],
            "rows": [["North", 25.0]],
            "row_count": 1,
        }
    )

    assert results.rows == [{"region": "North", "total_sales": 25.0}]
