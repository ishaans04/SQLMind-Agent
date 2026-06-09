import re


class UnsafeQueryError(ValueError):
    """Raised when a SQL statement is outside the read-only V1 policy."""


READ_ONLY_MODE_MESSAGE = "Command not allowed. SQLMind Agent is running in read-only mode."

BLOCKED_KEYWORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "grant",
    "insert",
    "merge",
    "pragma",
    "replace",
    "revoke",
    "truncate",
    "update",
    "vacuum",
}

ALLOWED_QUERY_PREFIXES = ("select ", "show ", "describe ", "explain ", "with ")


def validate_read_only_prompt(prompt: str) -> str:
    normalized = prompt.strip()
    if not normalized:
        raise UnsafeQueryError("Question cannot be empty.")

    tokens = set(re.findall(r"[a-z_]+", normalized.lower()))
    if tokens.intersection(BLOCKED_KEYWORDS):
        raise UnsafeQueryError(READ_ONLY_MODE_MESSAGE)

    return normalized


def validate_read_only_sql(sql: str) -> str:
    normalized = sql.strip()
    lowered = normalized.lower()

    if not normalized:
        raise UnsafeQueryError("SQL query cannot be empty.")
    if ";" in normalized.rstrip(";"):
        raise UnsafeQueryError("Only one SQL statement is allowed.")
    if not lowered.startswith(ALLOWED_QUERY_PREFIXES):
        raise UnsafeQueryError("Only read-only queries are allowed in V1.")

    tokens = set(re.findall(r"[a-z_]+", lowered))
    blocked = sorted(tokens.intersection(BLOCKED_KEYWORDS))
    if blocked:
        raise UnsafeQueryError(f"Blocked SQL keyword: {blocked[0]}.")

    return normalized.rstrip(";")


def apply_limit(sql: str, limit: int) -> str:
    if not sql.lower().lstrip().startswith(("select ", "with ")):
        return sql
    if re.search(r"\blimit\s+\d+\b", sql, flags=re.IGNORECASE):
        return sql
    return f"{sql} LIMIT {limit}"
