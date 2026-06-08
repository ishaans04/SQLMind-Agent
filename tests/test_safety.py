import pytest

from sqlmind_agent.safety import UnsafeQueryError, apply_limit, validate_read_only_sql


def test_validate_read_only_allows_select() -> None:
    assert validate_read_only_sql("SELECT * FROM sales;") == "SELECT * FROM sales"


def test_validate_read_only_blocks_mutation() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("DELETE FROM sales")


def test_apply_limit_preserves_existing_limit() -> None:
    assert apply_limit("SELECT * FROM sales LIMIT 5", 50) == "SELECT * FROM sales LIMIT 5"


def test_apply_limit_adds_limit() -> None:
    assert apply_limit("SELECT * FROM sales", 10) == "SELECT * FROM sales LIMIT 10"
