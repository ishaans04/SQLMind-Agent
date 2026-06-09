from typing import Any, Literal

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


class ConnectDatabaseRequest(BaseModel):
    db_type: Literal["sqlite", "postgresql", "mysql"]
    sqlite_file_path: str | None = Field(default=None, max_length=1_000)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65_535)
    database_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=1_000)


class ConnectDatabaseResponse(BaseModel):
    success: bool
    db_type: str
    message: str


class ConversationMemoryItem(BaseModel):
    question: str = Field(max_length=500)
    sql: str = Field(max_length=5_000)
    columns: list[str] = Field(default_factory=list)
    result_preview: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = Field(default="", max_length=2_000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int | None = Field(default=None, ge=1, le=500)
    conversation_history: list[ConversationMemoryItem] = Field(default_factory=list, max_length=10)


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
