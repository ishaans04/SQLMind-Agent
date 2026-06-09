from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio

from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.schemas import (
    ColumnInfo,
    ConnectDatabaseRequest,
    QueryResults,
    SchemaResponse,
    TableInfo,
)


class MCPClientError(RuntimeError):
    """Raised when SQLMind-MCP cannot be reached or returns an error."""


class SQLMindMCPClient:
    def __init__(
        self,
        server_path: Path,
        database_config: ConnectDatabaseRequest | None = None,
    ):
        self.server_path = server_path
        self.database_config = database_config

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        database_config: ConnectDatabaseRequest | None = None,
    ) -> SQLMindMCPClient:
        return cls(settings.mcp_server_path, database_config)

    def connect_database(self, config: ConnectDatabaseRequest) -> str:
        payload = self._call_tool("connect_database", {"config": _connection_config(config)})
        if not payload.get("success"):
            raise MCPClientError(payload.get("error", "SQLMind-MCP failed to connect database."))
        return str(payload.get("message", "Database connected."))

    def get_database_schema(self) -> SchemaResponse:
        payload = self._call_tool("get_database_schema", {})
        if not payload.get("success"):
            raise MCPClientError(payload.get("error", "SQLMind-MCP failed to fetch schema."))
        return _normalize_schema(payload)

    def run_select_query(self, sql: str) -> QueryResults:
        payload = self._call_tool("run_select_query", {"sql": sql})
        if not payload.get("success"):
            raise MCPClientError(payload.get("error", "SQLMind-MCP failed to execute query."))
        return _normalize_results(payload)

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return anyio.run(self._call_tool_async, tool_name, arguments)

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        server_path = self.server_path.expanduser()
        if not server_path.is_absolute():
            server_path = Path.cwd() / server_path
        server_path = server_path.resolve()

        if not server_path.exists():
            raise MCPClientError(f"SQLMind-MCP server not found at {server_path}.")

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            env = os.environ.copy()
            env.setdefault("SQLMIND_LOG_PATH", str((Path.cwd() / "data/mcp-query.log").resolve()))

            server_params = StdioServerParameters(
                command=sys.executable,
                args=[str(server_path)],
                env=env,
                cwd=str(server_path.parent),
            )
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    if self.database_config is not None and tool_name != "connect_database":
                        connect_result = await session.call_tool(
                            "connect_database",
                            arguments={"config": _connection_config(self.database_config)},
                        )
                        connect_payload = _extract_payload(connect_result)
                        if not connect_payload.get("success"):
                            raise MCPClientError(
                                connect_payload.get(
                                    "error",
                                    "SQLMind-MCP failed to connect database.",
                                )
                            )
                    result = await session.call_tool(tool_name, arguments=arguments)
        except MCPClientError:
            raise
        except Exception as error:
            raise MCPClientError(f"SQLMind-MCP could not start or respond: {error}") from error

        return _extract_payload(result)


def get_database_schema() -> SchemaResponse:
    return SQLMindMCPClient.from_settings(get_settings()).get_database_schema()


def run_select_query(sql: str) -> QueryResults:
    return SQLMindMCPClient.from_settings(get_settings()).run_select_query(sql)


def _connection_config(config: ConnectDatabaseRequest) -> dict[str, Any]:
    payload = config.model_dump(exclude_none=True)
    sqlite_file_path = payload.get("sqlite_file_path")
    if config.db_type == "sqlite" and isinstance(sqlite_file_path, str):
        path = Path(sqlite_file_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        payload["sqlite_file_path"] = str(path.resolve())
    return payload


def _extract_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structured_content", None) or getattr(
        result,
        "structuredContent",
        None,
    )
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as error:
                raise MCPClientError("SQLMind-MCP returned non-JSON tool content.") from error
            if isinstance(parsed, dict):
                return parsed

    if isinstance(result, dict):
        return result

    raise MCPClientError("SQLMind-MCP returned an unexpected tool response.")


def _normalize_schema(payload: dict[str, Any]) -> SchemaResponse:
    raw_schema = payload.get("schema")
    if not isinstance(raw_schema, dict):
        raise MCPClientError("SQLMind-MCP schema response is missing a schema object.")

    tables = [
        TableInfo(
            name=table_name,
            columns=[
                ColumnInfo(
                    name=str(column.get("name", "")),
                    type=str(column.get("type", "UNKNOWN") or "UNKNOWN"),
                    nullable=bool(column.get("nullable", True)),
                    primary_key=bool(column.get("primary_key", False)),
                )
                for column in columns
                if isinstance(column, dict)
            ],
        )
        for table_name, columns in raw_schema.items()
        if isinstance(columns, list)
    ]
    return SchemaResponse(tables=tables)


def _normalize_results(payload: dict[str, Any]) -> QueryResults:
    columns = [str(column) for column in payload.get("columns", [])]
    raw_rows = payload.get("rows", [])
    rows: list[dict[str, Any]] = []

    for row in raw_rows:
        if isinstance(row, dict):
            rows.append(row)
        elif isinstance(row, list):
            rows.append(dict(zip(columns, row, strict=False)))

    return QueryResults(
        columns=columns,
        rows=rows,
        row_count=int(payload.get("row_count", len(rows))),
    )
