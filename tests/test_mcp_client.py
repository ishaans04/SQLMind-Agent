from pathlib import Path
from types import SimpleNamespace

import pytest

from sqlmind_agent.mcp_client import (
    MCPClientError,
    SQLMindMCPClient,
    _connection_config,
    _extract_payload,
    _normalize_results,
    _normalize_schema,
)
from sqlmind_agent.schemas import ConnectDatabaseRequest


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


def test_connect_database_calls_mcp_tool_without_redacting_payload() -> None:
    calls: list[tuple[str, dict]] = []

    class FakeMCPClient(SQLMindMCPClient):
        def _call_tool(self, tool_name: str, arguments: dict) -> dict:
            calls.append((tool_name, arguments))
            return {"success": True, "message": "Connected."}

    config = ConnectDatabaseRequest(
        db_type="mysql",
        host="localhost",
        port=3306,
        database_name="school",
        username="admin",
        password="secret",
    )

    message = FakeMCPClient(server_path="server.py").connect_database(config)

    assert message == "Connected."
    assert calls == [
        (
            "connect_database",
            {
                "config": {
                    "db_type": "mysql",
                    "host": "localhost",
                    "port": 3306,
                    "database_name": "school",
                    "username": "admin",
                    "password": "secret",
                }
            },
        )
    ]


def test_sqlite_connection_config_uses_absolute_path() -> None:
    payload = _connection_config(
        ConnectDatabaseRequest(db_type="sqlite", sqlite_file_path="data/demo.db")
    )

    path = Path(payload["sqlite_file_path"])
    assert path.is_absolute()
    assert path.name == "demo.db"

