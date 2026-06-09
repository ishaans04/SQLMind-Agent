from __future__ import annotations

import json
from typing import Any

from sqlmind_agent.nim_client import NIMClient, NIMClientError
from sqlmind_agent.schemas import AnalysisPlanStep, ExecutedAnalysisStep

ANALYSIS_PLAN_SYSTEM_PROMPT = """
You are SQLMind-Agent's Smart Analytics planner.
Create 3 to 5 safe, read-only SQL analysis steps for the user's broad analytical request.
Each step must use only the provided schema.
Each sql_query must be SELECT-only or WITH ... SELECT.
Return ONLY valid JSON, no markdown.
The JSON shape must be:
{"steps":[{"step_title":"...","purpose":"...","sql_query":"SELECT ..."}]}
""".strip()


FINAL_REPORT_SYSTEM_PROMPT = """
You are SQLMind-Agent's senior analytics narrator.
Write a concise final insight report from the executed analysis steps.
Mention failed steps briefly if present. Do not invent facts beyond the provided summaries.
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
        payload = _parse_json_object(content)
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            raise NIMClientError("NVIDIA NIM analysis plan response is missing steps.")
        steps = [AnalysisPlanStep.model_validate(step) for step in raw_steps[:5]]
        if len(steps) < 3:
            raise NIMClientError("NVIDIA NIM analysis plan must contain at least 3 steps.")
        return steps

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


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise NIMClientError("NVIDIA NIM analysis plan response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise NIMClientError("NVIDIA NIM analysis plan response must be a JSON object.")
    return payload
