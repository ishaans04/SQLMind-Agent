import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlmind_agent.schemas import ColumnInfo, TableInfo


class DatabaseClient:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.database_path}. Run scripts/init_demo_db.py first."
            )
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def schema(self) -> list[TableInfo]:
        with self.connect() as connection:
            table_rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            tables: list[TableInfo] = []
            for table in table_rows:
                table_name = table["name"]
                column_rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                tables.append(
                    TableInfo(
                        name=table_name,
                        columns=[
                            ColumnInfo(
                                name=row["name"],
                                type=row["type"] or "UNKNOWN",
                                nullable=not bool(row["notnull"]),
                                primary_key=bool(row["pk"]),
                            )
                            for row in column_rows
                        ],
                    )
                )
            return tables

    def execute(self, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        with self.connect() as connection:
            cursor = connection.execute(sql)
            columns = [description[0] for description in cursor.description or []]
            rows = [dict(row) for row in cursor.fetchall()]
            return columns, rows


def known_table_names(tables: Iterable[TableInfo]) -> set[str]:
    return {table.name.lower() for table in tables}
