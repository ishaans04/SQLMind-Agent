from typing import Any

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]


class SchemaResponse(BaseModel):
    tables: list[TableInfo]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int | None = Field(default=None, ge=1, le=500)


class QueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5_000)
    limit: int | None = Field(default=None, ge=1, le=500)


class QueryResults(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class AskResponse(BaseModel):
    question: str
    sql: str
    results: QueryResults
    explanation: str


class QueryResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    explanation: str
