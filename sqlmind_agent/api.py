from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.database import DatabaseClient
from sqlmind_agent.nim_client import MissingNvidiaApiKeyError, NIMClient, NIMClientError
from sqlmind_agent.safety import UnsafeQueryError, apply_limit, validate_read_only_sql
from sqlmind_agent.schemas import (
    AskRequest,
    AskResponse,
    QueryRequest,
    QueryResponse,
    QueryResults,
    SchemaResponse,
)

app = FastAPI(title="SQLMind-Agent", version="0.1.0")


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_database(settings: SettingsDep) -> DatabaseClient:
    return DatabaseClient(settings.database_path)


DatabaseDep = Annotated[DatabaseClient, Depends(get_database)]


def get_nim_client(settings: SettingsDep) -> NIMClient:
    return NIMClient.from_settings(settings)


NIMClientDep = Annotated[NIMClient, Depends(get_nim_client)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/schema", response_model=SchemaResponse)
def schema(database: DatabaseDep) -> SchemaResponse:
    try:
        return SchemaResponse(tables=database.schema())
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    settings: SettingsDep,
    database: DatabaseDep,
    nim_client: NIMClientDep,
) -> AskResponse:
    try:
        tables = database.schema()
        schema_dict = SchemaResponse(tables=tables).model_dump()
        sql = nim_client.generate_sql(request.question, schema_dict)
        limited_sql = apply_limit(
            validate_read_only_sql(sql),
            request.limit or settings.default_limit,
        )
        columns, rows = database.execute(limited_sql)
        results = QueryResults(columns=columns, rows=rows, row_count=len(rows))
        explanation = nim_client.explain_results(
            request.question,
            limited_sql,
            results.model_dump(),
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except MissingNvidiaApiKeyError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except NIMClientError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except UnsafeQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Query failed: {error}") from error

    return AskResponse(
        question=request.question,
        sql=limited_sql,
        results=results,
        explanation=explanation,
    )


@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    settings: SettingsDep,
    database: DatabaseDep,
) -> QueryResponse:
    try:
        sql = apply_limit(
            validate_read_only_sql(request.sql),
            request.limit or settings.default_limit,
        )
        columns, rows = database.execute(sql)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except UnsafeQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Query failed: {error}") from error

    return QueryResponse(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        explanation="Executed the provided read-only SQL query.",
    )
