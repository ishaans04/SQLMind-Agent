from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from sqlmind_agent.nim_client import NIMClient, NIMClientError
from sqlmind_agent.schemas import AnalysisPlanStep, ExecutedAnalysisStep

ANALYSIS_PLAN_SYSTEM_PROMPT = """
You are SQLMind-Agent's Smart Analytics planner.
Create 3 to 5 safe, read-only SQL analysis steps for the user's broad analytical request.
Each step must use only the provided schema.
Each sql_query must be SELECT-only or WITH ... SELECT.
Return raw JSON only.
Do not include markdown.
Do not include explanations.
Do not include code fences.
The JSON shape must be:
{"steps":[{"step_title":"...","purpose":"...","sql_query":"SELECT ..."}]}
""".strip()


FINAL_REPORT_SYSTEM_PROMPT = """
You are SQLMind-Agent's senior analytics narrator.
Write a concise final insight report from the executed analysis steps as clean Markdown.
Mention failed steps briefly if present. Do not invent facts beyond the provided summaries.
Return clean Markdown only. Do not include code fences. Do not include JSON.
Do not include unnecessary blank lines. Do not write "Here is".
Use this exact structure:

# Smart Analysis Report

## Executive Summary
Short summary of what was analyzed.

## Key Findings
- Finding 1
- Finding 2
- Finding 3

## Supporting Metrics
- Metric 1
- Metric 2

## Recommendations
- Recommendation 1
- Recommendation 2

## Attention Areas
- Risk or weak area 1
- Risk or weak area 2

Avoid repeated titles, broken numbered lists, single huge paragraphs, and vague generic
statements. Each section should be grounded in the executed step results.
""".strip()


class AnalysisPlanner:
    def __init__(self, nim_client: NIMClient):
        self.nim_client = nim_client

    def generate_plan(self, question: str, schema: dict[str, Any]) -> list[AnalysisPlanStep]:
        content = self.nim_client._chat(
            messages=[
                {"role": "system", "content": ANALYSIS_PLAN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Schema:\n{schema}\n\nAnalysis request:\n{question}",
                },
            ],
            temperature=0.1,
        )
        try:
            return _steps_from_payload(_parse_json_object(content))
        except (NIMClientError, ValidationError, TypeError, ValueError):
            try:
                return fallback_analysis_plan(question, schema)
            except Exception as fallback_error:
                raise NIMClientError(
                    "Smart Analysis could not parse the NVIDIA NIM plan response "
                    "and fallback plan creation failed."
                ) from fallback_error

    def final_report(self, question: str, executed_steps: list[ExecutedAnalysisStep]) -> str:
        step_payload = [step.model_dump() for step in executed_steps]
        return self.nim_client._chat(
            messages=[
                {"role": "system", "content": FINAL_REPORT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Original question:\n{question}\n\nExecuted steps:\n{step_payload}",
                },
            ],
            temperature=0.2,
        ).strip()


def summarize_results(step: ExecutedAnalysisStep) -> str:
    if not step.success or step.results is None:
        return f"{step.step_title}: failed - {step.error}"
    columns = ", ".join(step.results.columns)
    return f"{step.step_title}: returned {step.results.row_count} rows with columns {columns}."


def suggest_chart(step: ExecutedAnalysisStep) -> str:
    if not step.success or step.results is None:
        return f"{step.step_title}: no chart suggestion because the step failed."
    rows = step.results.rows
    numeric_columns = [
        column
        for column in step.results.columns
        if any(isinstance(row.get(column), int | float) for row in rows)
    ]
    if not rows or not numeric_columns:
        return f"{step.step_title}: no chart suggested; no numeric result columns."
    date_columns = [
        column
        for column in step.results.columns
        if "date" in column.lower() or "time" in column.lower()
    ]
    category_columns = [
        column for column in step.results.columns if column not in numeric_columns + date_columns
    ]
    if date_columns:
        return f"{step.step_title}: line chart using {date_columns[0]} and {numeric_columns[0]}."
    if category_columns:
        return f"{step.step_title}: bar chart using {category_columns[0]} and {numeric_columns[0]}."
    return f"{step.step_title}: table view recommended."


def fallback_analysis_plan(question: str, schema: dict[str, Any]) -> list[AnalysisPlanStep]:
    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, list) or not tables:
        return [
            AnalysisPlanStep(
                step_title="Baseline Check",
                purpose=f"Create a safe starter step for: {question}",
                sql_query="SELECT 1 AS baseline_value",
            ),
            AnalysisPlanStep(
                step_title="Record Availability",
                purpose="Confirm the analysis can run without modifying data.",
                sql_query="SELECT 1 AS available",
            ),
            AnalysisPlanStep(
                step_title="Preview Metric",
                purpose="Return a simple read-only preview metric.",
                sql_query="SELECT 1 AS preview_value",
            ),
        ]

    first_table = _table_name(tables[0])
    second_table = _table_name(tables[1]) if len(tables) > 1 else first_table
    first_columns = _table_columns(tables[0])
    text_column = _first_column_by_type(first_columns, ("text", "char", "varchar", "string"))
    numeric_column = _first_column_by_type(
        first_columns,
        ("int", "real", "numeric", "decimal", "double", "float"),
    )

    safe_first_table = _quote_identifier(first_table)
    safe_second_table = _quote_identifier(second_table)
    steps = [
        AnalysisPlanStep(
            step_title=f"{first_table} Record Count",
            purpose=f"Measure available records for the primary table related to: {question}",
            sql_query=f"SELECT COUNT(*) AS total_records FROM {safe_first_table}",
        ),
        AnalysisPlanStep(
            step_title=f"{first_table} Preview",
            purpose="Inspect a safe preview of the primary table.",
            sql_query=f"SELECT * FROM {safe_first_table}",
        ),
        AnalysisPlanStep(
            step_title=f"{second_table} Record Count",
            purpose="Compare availability across another table when present.",
            sql_query=f"SELECT COUNT(*) AS total_records FROM {safe_second_table}",
        ),
    ]

    if text_column and numeric_column:
        safe_text = _quote_identifier(text_column)
        safe_numeric = _quote_identifier(numeric_column)
        steps[1] = AnalysisPlanStep(
            step_title=f"{numeric_column} by {text_column}",
            purpose="Summarize the first available numeric metric by category.",
            sql_query=(
                f"SELECT {safe_text}, AVG({safe_numeric}) AS avg_{numeric_column} "
                f"FROM {safe_first_table} GROUP BY {safe_text} "
                f"ORDER BY avg_{numeric_column} DESC"
            ),
        )
    elif numeric_column:
        safe_numeric = _quote_identifier(numeric_column)
        steps[1] = AnalysisPlanStep(
            step_title=f"{numeric_column} Summary",
            purpose="Summarize the first available numeric metric.",
            sql_query=(
                f"SELECT AVG({safe_numeric}) AS avg_{numeric_column}, "
                f"MIN({safe_numeric}) AS min_{numeric_column}, "
                f"MAX({safe_numeric}) AS max_{numeric_column} "
                f"FROM {safe_first_table}"
            ),
        )

    return steps


def _parse_json_object(content: str) -> dict[str, Any]:
    text = _clean_json_content(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise NIMClientError("NVIDIA NIM analysis plan response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise NIMClientError("NVIDIA NIM analysis plan response must be a JSON object.")
    return payload


def _clean_json_content(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]
    return text.strip()


def _steps_from_payload(payload: dict[str, Any]) -> list[AnalysisPlanStep]:
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise NIMClientError("NVIDIA NIM analysis plan response is missing steps.")
    steps = [AnalysisPlanStep.model_validate(step) for step in raw_steps[:5]]
    if len(steps) < 3:
        raise NIMClientError("NVIDIA NIM analysis plan must contain at least 3 steps.")
    return steps


def _table_name(table: Any) -> str:
    if isinstance(table, dict):
        name = table.get("name")
        if name:
            return str(name)
    return "data"


def _table_columns(table: Any) -> list[dict[str, Any]]:
    if not isinstance(table, dict):
        return []
    columns = table.get("columns")
    if not isinstance(columns, list):
        return []
    return [column for column in columns if isinstance(column, dict)]


def _first_column_by_type(
    columns: list[dict[str, Any]],
    type_fragments: tuple[str, ...],
) -> str | None:
    for column in columns:
        column_type = str(column.get("type", "")).lower()
        if any(fragment in column_type for fragment in type_fragments):
            return str(column.get("name"))
    return None


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
