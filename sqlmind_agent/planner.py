import re

from sqlmind_agent.database import known_table_names
from sqlmind_agent.schemas import TableInfo


class QueryPlanner:
    """Deterministic starter planner for V1.

    This keeps the product usable before an LLM planner is wired in.
    """

    def plan(self, question: str, schema: list[TableInfo]) -> tuple[str, str]:
        text = question.lower()

        if "total" in text and "sales" in text and self._has_table(schema, "sales"):
            if "region" in text:
                return (
                    "SELECT region, ROUND(SUM(amount), 2) AS total_sales "
                    "FROM sales GROUP BY region ORDER BY total_sales DESC",
                    "Grouped sales by region and summed the amount column.",
                )
            if "product" in text:
                return (
                    "SELECT product, ROUND(SUM(amount), 2) AS total_sales "
                    "FROM sales GROUP BY product ORDER BY total_sales DESC",
                    "Grouped sales by product and summed the amount column.",
                )
            return (
                "SELECT ROUND(SUM(amount), 2) AS total_sales FROM sales",
                "Summed the amount column from the sales table.",
            )

        table_name = self._mentioned_table(text, schema)
        if table_name:
            return (
                f'SELECT * FROM "{table_name}"',
                f"Selected rows from the {table_name} table because it was mentioned.",
            )

        first_table = schema[0].name if schema else None
        if first_table:
            return (
                f'SELECT * FROM "{first_table}"',
                f"Selected rows from the first available table, {first_table}.",
            )

        return "SELECT 1 AS result", "No user tables were found, so returned a simple test query."

    def _has_table(self, schema: list[TableInfo], table_name: str) -> bool:
        return table_name.lower() in known_table_names(schema)

    def _mentioned_table(self, text: str, schema: list[TableInfo]) -> str | None:
        words = set(re.findall(r"[a-z0-9_]+", text))
        for table in schema:
            if table.name.lower() in words:
                return table.name
        return None
