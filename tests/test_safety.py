import pytest

from sqlmind_agent.safety import (
    READ_ONLY_MODE_MESSAGE,
    UnsafeQueryError,
    apply_limit,
    validate_read_only_prompt,
    validate_read_only_sql,
)


def test_validate_read_only_allows_select() -> None:
    assert validate_read_only_sql("SELECT * FROM sales;") == "SELECT * FROM sales"


def test_validate_read_only_blocks_mutation() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("DELETE FROM sales")


@pytest.mark.parametrize(
    "sql",
    [
        "SHOW TABLES",
        "DESCRIBE sales",
        "EXPLAIN SELECT * FROM sales",
        "WITH totals AS (SELECT 1 AS value) SELECT * FROM totals",
    ],
)
def test_validate_read_only_allows_read_only_prefixes(sql: str) -> None:
    assert validate_read_only_sql(sql) == sql


@pytest.mark.parametrize(
    "prompt",
    [
        "drop the students table",
        "delete all rows",
        "truncate marks",
        "update fees",
        "insert a student",
        "alter the schema",
        "create a table",
        "replace rows",
        "merge records",
        "grant access",
        "revoke access",
    ],
)
def test_validate_read_only_prompt_blocks_mutation_intent(prompt: str) -> None:
    with pytest.raises(UnsafeQueryError, match=READ_ONLY_MODE_MESSAGE):
        validate_read_only_prompt(prompt)


def test_validate_read_only_prompt_allows_read_only_question() -> None:
    assert validate_read_only_prompt("show total sales by region") == "show total sales by region"


def test_apply_limit_preserves_existing_limit() -> None:
    assert apply_limit("SELECT * FROM sales LIMIT 5", 50) == "SELECT * FROM sales LIMIT 5"


def test_apply_limit_adds_limit() -> None:
    assert apply_limit("SELECT * FROM sales", 10) == "SELECT * FROM sales LIMIT 10"


def test_apply_limit_ignores_non_select_read_only_queries() -> None:
    assert apply_limit("SHOW TABLES", 10) == "SHOW TABLES"
