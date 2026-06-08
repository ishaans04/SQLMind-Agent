import re


class UnsafeQueryError(ValueError):
    """Raised when a SQL statement is outside the read-only V1 policy."""


BLOCKED_KEYWORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "insert",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}


def validate_read_only_sql(sql: str) -> str:
    normalized = sql.strip()
    lowered = normalized.lower()

    if not normalized:
        raise UnsafeQueryError("SQL query cannot be empty.")
    if ";" in normalized.rstrip(";"):
        raise UnsafeQueryError("Only one SQL statement is allowed.")
    if not lowered.startswith(("select ", "with ")):
        raise UnsafeQueryError("Only SELECT queries are allowed in V1.")

    tokens = set(re.findall(r"[a-z_]+", lowered))
    blocked = sorted(tokens.intersection(BLOCKED_KEYWORDS))
    if blocked:
        raise UnsafeQueryError(f"Blocked SQL keyword: {blocked[0]}.")

    return normalized.rstrip(";")


def apply_limit(sql: str, limit: int) -> str:
    if re.search(r"\blimit\s+\d+\b", sql, flags=re.IGNORECASE):
        return sql
    return f"{sql} LIMIT {limit}"
