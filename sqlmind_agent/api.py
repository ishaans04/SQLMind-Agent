import sys
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.dependency_check import MYSQL_AVAILABLE, mysql_dependency_error
from sqlmind_agent.mcp_client import MCPClientError, SQLMindMCPClient
from sqlmind_agent.nim_client import MissingNvidiaApiKeyError, NIMClient, NIMClientError
from sqlmind_agent.safety import (
    UnsafeQueryError,
    apply_limit,
    validate_read_only_prompt,
    validate_read_only_sql,
)
from sqlmind_agent.schemas import (
    AskRequest,
    AskResponse,
    ConnectDatabaseRequest,
    ConnectDatabaseResponse,
    QueryRequest,
    QueryResponse,
    SchemaResponse,
)

app = FastAPI(title="SQLMind-Agent", version="0.1.0")
print(f"SQLMind-Agent FastAPI Python executable: {sys.executable}")


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_active_database_config() -> ConnectDatabaseRequest | None:
    value = getattr(app.state, "database_config", None)
    return value if isinstance(value, ConnectDatabaseRequest) else None


def get_mcp_client(settings: SettingsDep) -> SQLMindMCPClient:
    return SQLMindMCPClient.from_settings(settings, get_active_database_config())


MCPClientDep = Annotated[SQLMindMCPClient, Depends(get_mcp_client)]


def get_connection_mcp_client(settings: SettingsDep) -> SQLMindMCPClient:
    return SQLMindMCPClient.from_settings(settings)


ConnectionMCPClientDep = Annotated[SQLMindMCPClient, Depends(get_connection_mcp_client)]


def get_nim_client(settings: SettingsDep) -> NIMClient:
    return NIMClient.from_settings(settings)


NIMClientDep = Annotated[NIMClient, Depends(get_nim_client)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/schema", response_model=SchemaResponse)
def schema(mcp_client: MCPClientDep) -> SchemaResponse:
    try:
        return mcp_client.get_database_schema()
    except MCPClientError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/connect-database", response_model=ConnectDatabaseResponse)
def connect_database(
    request: ConnectDatabaseRequest,
    mcp_client: ConnectionMCPClientDep,
) -> ConnectDatabaseResponse:
    try:
        _validate_database_request(request)
        message = mcp_client.connect_database(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except MCPClientError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    app.state.database_config = request
    return ConnectDatabaseResponse(
        success=True,
        db_type=request.db_type,
        message=message,
    )


@app.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    settings: SettingsDep,
    mcp_client: MCPClientDep,
    nim_client: NIMClientDep,
) -> AskResponse:
    try:
        question = validate_read_only_prompt(request.question)
        schema_response = mcp_client.get_database_schema()
        schema_dict = schema_response.model_dump()
        conversation_history = [
            item.model_dump()
            for item in request.conversation_history
        ]
        sql = nim_client.generate_sql(question, schema_dict, conversation_history)
        limited_sql = apply_limit(
            validate_read_only_sql(sql),
            request.limit or settings.default_limit,
        )
        results = mcp_client.run_select_query(limited_sql)
        explanation = nim_client.explain_results(
            question,
            limited_sql,
            results.model_dump(),
        )
    except MCPClientError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except MissingNvidiaApiKeyError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except NIMClientError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except UnsafeQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Query failed: {error}") from error

    return AskResponse(
        question=question,
        sql=limited_sql,
        results=results,
        explanation=explanation,
    )


def _validate_database_request(request: ConnectDatabaseRequest) -> None:
    if request.db_type == "sqlite":
        if not request.sqlite_file_path:
            raise ValueError("sqlite_file_path is required for SQLite connections.")
        return

    if request.db_type == "mysql" and not MYSQL_AVAILABLE:
        raise ValueError(mysql_dependency_error())

    missing = [
        field_name
        for field_name in ("host", "port", "database_name", "username")
        if getattr(request, field_name) in (None, "")
    ]
    if missing:
        raise ValueError(f"Missing required database connection fields: {', '.join(missing)}.")


@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    settings: SettingsDep,
    mcp_client: MCPClientDep,
) -> QueryResponse:
    try:
        sql = apply_limit(
            validate_read_only_sql(request.sql),
            request.limit or settings.default_limit,
        )
        results = mcp_client.run_select_query(sql)
    except MCPClientError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except UnsafeQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Query failed: {error}") from error

    return QueryResponse(
        sql=sql,
        columns=results.columns,
        rows=results.rows,
        row_count=results.row_count,
        explanation="Executed the provided read-only SQL query.",
    )
