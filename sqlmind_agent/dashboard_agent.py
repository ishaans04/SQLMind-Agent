from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from sqlmind_agent.nim_client import NIMClient, NIMClientError
from sqlmind_agent.schemas import DashboardPlan, DashboardWidgetResult

DASHBOARD_PLAN_SYSTEM_PROMPT = """
You are SQLMind-Agent's executive dashboard designer.
Create a read-only analytics dashboard plan for the user's broad dashboard request.
Use only the provided schema.
Every widget must include one safe SELECT-only or WITH ... SELECT SQL query.
Return ONLY valid JSON, no markdown.
The JSON shape must be:
{
  "dashboard_title": "...",
  "kpi_cards": [{"title": "...", "purpose": "...", "sql_query": "SELECT ..."}],
  "chart_widgets": [{"title": "...", "purpose": "...", "sql_query": "SELECT ..."}],
  "table_widgets": [{"title": "...", "purpose": "...", "sql_query": "SELECT ..."}],
  "insight_goals": ["..."]
}
Prefer 2 to 4 KPI cards, 2 to 4 chart widgets, and 1 to 3 table widgets.
For distribution chart widgets, do not return raw numeric rows.
Generate bucketed SELECT queries with a category/range column and a count column.
For example, marks distribution should return mark_range and student_count.
Use CASE expressions plus COUNT(*) for numeric ranges when the schema contains marks, scores,
attendance, fees, or other numeric measures.
""".strip()


DASHBOARD_REPORT_SYSTEM_PROMPT = """
You are SQLMind-Agent's executive analytics narrator.
Write a concise final insight report for the generated dashboard as clean Markdown.
Mention failed widgets briefly if present. Do not invent facts beyond the provided widget results.
Return ONLY Markdown, no code fences.
Use this exact structure:

# Final Insight Report

## Executive Summary
Brief overview of the dashboard.

## Key Metrics
1. **Average Student Marks**
   Explanation.

2. **Total Students**
   Explanation.

3. **Average Attendance**
   Explanation.

## Branch-wise Analysis
- **CSE:** insight
- **ITE:** insight
- **AI-DS:** insight
- **ECE:** insight

## Key Findings
- Finding 1
- Finding 2
- Finding 3

## Recommendations
- Recommendation 1
- Recommendation 2
- Recommendation 3

## Attention Areas
- Risk or weak area 1
- Risk or weak area 2

If a section is not directly supported by the available widget results, keep it brief and say
that the dashboard data does not include enough evidence for that section.
""".strip()


class DashboardAgent:
    def __init__(self, nim_client: NIMClient):
        self.nim_client = nim_client

    def generate_plan(self, prompt: str, schema: dict[str, Any]) -> DashboardPlan:
        content = self.nim_client._chat(
            messages=[
                {"role": "system", "content": DASHBOARD_PLAN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Schema:\n{schema}\n\nDashboard request:\n{prompt}",
                },
            ],
            temperature=0.1,
        )
        try:
            payload = _parse_json_object(content)
            plan = DashboardPlan.model_validate(payload)
        except (NIMClientError, ValidationError, TypeError, ValueError):
            return fallback_dashboard_plan(prompt, schema)

        if not plan.kpi_cards and not plan.chart_widgets and not plan.table_widgets:
            return fallback_dashboard_plan(prompt, schema)
        return plan

    def final_report(
        self,
        prompt: str,
        plan: DashboardPlan,
        kpis: list[DashboardWidgetResult],
        charts: list[DashboardWidgetResult],
        tables: list[DashboardWidgetResult],
    ) -> str:
        widget_payload = {
            "dashboard_title": plan.dashboard_title,
            "insight_goals": plan.insight_goals,
            "kpis": [widget.model_dump() for widget in kpis],
            "charts": [widget.model_dump() for widget in charts],
            "tables": [widget.model_dump() for widget in tables],
        }
        return self.nim_client._chat(
            messages=[
                {"role": "system", "content": DASHBOARD_REPORT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Dashboard request:\n{prompt}\n\nWidget results:\n{widget_payload}",
                },
            ],
            temperature=0.2,
        ).strip()


def fallback_dashboard_plan(prompt: str, schema: dict[str, Any]) -> DashboardPlan:
    tables = schema.get("tables") if isinstance(schema, dict) else None
    first_table = tables[0] if isinstance(tables, list) and tables else {}
    table_name = str(first_table.get("name", "data"))
    columns = first_table.get("columns") if isinstance(first_table, dict) else []
    if not isinstance(columns, list):
        columns = []
    text_column = _first_column_by_type(columns, ("text", "char", "varchar", "string"))
    numeric_column = _first_column_by_type(
        columns,
        ("int", "real", "numeric", "decimal", "double", "float"),
    )

    safe_table = _quote_identifier(table_name)
    table_sql = f"SELECT * FROM {safe_table}"
    kpi_sql = f"SELECT COUNT(*) AS total_records FROM {safe_table}"

    chart_widgets = []
    if text_column and numeric_column:
        safe_text = _quote_identifier(text_column)
        safe_numeric = _quote_identifier(numeric_column)
        chart_widgets.append(
            {
                "title": f"{numeric_column} by {text_column}",
                "purpose": "Compare the first available numeric metric by category.",
                "sql_query": (
                    f"SELECT {safe_text}, SUM({safe_numeric}) AS total_{numeric_column} "
                    f"FROM {safe_table} GROUP BY {safe_text} "
                    f"ORDER BY total_{numeric_column} DESC"
                ),
            }
        )
    elif numeric_column:
        safe_numeric = _quote_identifier(numeric_column)
        chart_widgets.append(
            {
                "title": f"{numeric_column} distribution",
                "purpose": "Review the first available numeric metric by bucket.",
                "sql_query": _numeric_bucket_sql(safe_table, safe_numeric, numeric_column),
            }
        )

    return DashboardPlan(
        dashboard_title=_fallback_title(prompt),
        kpi_cards=[
            {
                "title": "Total Records",
                "purpose": "Count available records in the primary table.",
                "sql_query": kpi_sql if table_name != "data" else "SELECT 1 AS total_records",
            }
        ],
        chart_widgets=chart_widgets,
        table_widgets=[
            {
                "title": f"{table_name.title()} Preview",
                "purpose": "Show a preview of the primary table.",
                "sql_query": table_sql if table_name != "data" else "SELECT 1 AS value",
            }
        ],
        insight_goals=[
            "Summarize the highest-level metrics available from the connected schema.",
            "Identify visible patterns without modifying data.",
        ],
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise NIMClientError("NVIDIA NIM dashboard plan response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise NIMClientError("NVIDIA NIM dashboard plan response must be a JSON object.")
    return payload


def _first_column_by_type(columns: Any, type_fragments: tuple[str, ...]) -> str | None:
    if not isinstance(columns, list):
        return None
    for column in columns:
        if not isinstance(column, dict):
            continue
        column_type = str(column.get("type", "")).lower()
        if any(fragment in column_type for fragment in type_fragments):
            return str(column.get("name"))
    return None


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _numeric_bucket_sql(safe_table: str, safe_numeric: str, numeric_column: str) -> str:
    range_column = f"{numeric_column}_range"
    count_column = f"{numeric_column}_count"
    return (
        "SELECT "
        f"CASE WHEN {safe_numeric} IS NULL THEN 'Unknown' "
        f"WHEN {safe_numeric} < 40 THEN '<40' "
        f"WHEN {safe_numeric} < 60 THEN '40-59' "
        f"WHEN {safe_numeric} < 80 THEN '60-79' "
        f"ELSE '80+' END AS {_quote_identifier(range_column)}, "
        f"COUNT(*) AS {_quote_identifier(count_column)} "
        f"FROM {safe_table} "
        f"GROUP BY CASE WHEN {safe_numeric} IS NULL THEN 'Unknown' "
        f"WHEN {safe_numeric} < 40 THEN '<40' "
        f"WHEN {safe_numeric} < 60 THEN '40-59' "
        f"WHEN {safe_numeric} < 80 THEN '60-79' "
        "ELSE '80+' END "
        f"ORDER BY {_quote_identifier(range_column)}"
    )


def _fallback_title(prompt: str) -> str:
    cleaned = prompt.strip().rstrip(".")
    if not cleaned:
        return "Executive Analytics Dashboard"
    return cleaned[:1].upper() + cleaned[1:]
