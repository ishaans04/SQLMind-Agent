from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from sqlmind_agent.nim_client import NIMClient, NIMClientError
from sqlmind_agent.schemas import AnalysisPlanStep, ExecutedAnalysisStep

ANALYSIS_PLAN_SYSTEM_PROMPT = """
You are SQLMind-Agent's Smart Analytics planner.
Behave like a senior business analyst, not a database statistics tool.
Before writing SQL, inspect the schema context for fact tables, dimension tables, and
foreign-key style relationships.
Create 3 to 5 safe, read-only SQL analysis steps for the user's broad analytical request.
Smart Analysis is for multi-query investigation: each step must answer a distinct
sub-question that contributes to the original request.
Each step must use only the provided schema.
Each sql_query must be SELECT-only or WITH ... SELECT.
Use the identifier quoting style specified by the database dialect context.
Every sql_query must be one complete SQL string ending with a semicolon.
Use joins whenever relationships exist.
When a query uses JOIN, always fully qualify table and column references in SELECT,
GROUP BY, ORDER BY, HAVING, and aggregate expressions using table aliases or table names.
Never use ambiguous unqualified columns such as product_id after joining tables that both
contain product_id.
Use subqueries or CTEs when they make the analytical step clearer, for example rankings,
percent-of-total, cohorts, distributions, or risk segmentation.
Do not create a plan where every step is a shallow variation of the same top-level query.
Prioritize business metrics such as revenue, sales, quantity, attendance, marks,
performance, averages, trends, risks, opportunities, and recommendations.
For sales analysis, prefer revenue by region, revenue by product, top-selling products,
category performance, customer segment analysis, and trend/risk views.
Never analyze technical identifier fields such as id, customer_id, product_id, order_id,
student_id, or *_id as metrics unless the user explicitly asks for identifiers.
Do not create steps like average id value, min id value, max id value, or id distribution.
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
Tie every finding to the original question and the executed step results.
Synthesize every successful executed SQL step. Do not base the report only on the first
or highest-level query.
Include a query-by-query findings section where each executed step gets its own bullet
or subsection with the relevant result values.
If the executed steps indicate the connected schema does not contain the requested domain
fields, say that clearly instead of switching to another business domain.
Do not discuss sales, revenue, products, or customers for a student performance request
unless those fields appear in the executed steps.
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
- Step 1: metric or observation from the executed results
- Step 2: metric or observation from the executed results
- Step 3: metric or observation from the executed results

## Query-by-Query Findings
- Step title: specific finding from that query result
- Step title: specific finding from that query result

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

    def generate_plan(
        self,
        question: str,
        schema: dict[str, Any],
        db_type: str = "sqlite",
    ) -> list[AnalysisPlanStep]:
        schema_profile = inspect_schema_for_analysis(schema)
        content = self.nim_client._chat(
            messages=[
                {"role": "system", "content": ANALYSIS_PLAN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Schema:\n{schema}\n\n"
                        f"Schema business profile:\n{schema_profile.to_prompt_context()}\n\n"
                        f"Database dialect:\n{_dialect_prompt_context(db_type)}\n\n"
                        f"Analysis request:\n{question}"
                    ),
                },
            ],
            temperature=0.1,
        )
        try:
            steps = _normalize_steps_for_db(
                _steps_from_payload(_parse_json_object(content)),
                schema,
                db_type,
            )
            if _contains_low_value_technical_analysis(
                steps,
                question,
            ) or _contains_intent_mismatch(steps, question):
                return fallback_analysis_plan(question, schema, db_type)
            return steps
        except (NIMClientError, ValidationError, TypeError, ValueError):
            try:
                return fallback_analysis_plan(question, schema, db_type)
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


def fallback_analysis_plan(
    question: str,
    schema: dict[str, Any],
    db_type: str = "sqlite",
) -> list[AnalysisPlanStep]:
    profile = inspect_schema_for_analysis(schema)
    business_steps = _business_fallback_steps(question, profile, db_type)
    if business_steps:
        return business_steps[:5]

    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, list) or not tables:
        return [
            AnalysisPlanStep(
                step_title="Baseline Check",
                purpose=f"Create a safe starter step for: {question}",
                sql_query=_complete_sql("SELECT 1 AS baseline_value"),
            ),
            AnalysisPlanStep(
                step_title="Record Availability",
                purpose="Confirm the analysis can run without modifying data.",
                sql_query=_complete_sql("SELECT 1 AS available"),
            ),
            AnalysisPlanStep(
                step_title="Preview Metric",
                purpose="Return a simple read-only preview metric.",
                sql_query=_complete_sql("SELECT 1 AS preview_value"),
            ),
        ]

    first_table = _table_name(tables[0])
    second_table = _table_name(tables[1]) if len(tables) > 1 else first_table
    first_columns = _table_columns(tables[0])
    text_column = _first_column_by_type(first_columns, ("text", "char", "varchar", "string"))
    numeric_column = _first_business_numeric_column(
        first_columns,
        ("int", "real", "numeric", "decimal", "double", "float"),
    )

    safe_first_table = _quote_identifier(first_table, db_type)
    safe_second_table = _quote_identifier(second_table, db_type)
    steps = [
        AnalysisPlanStep(
            step_title=f"{first_table} Volume",
            purpose=f"Measure business volume for the primary table related to: {question}",
            sql_query=_complete_sql(f"SELECT COUNT(*) AS total_records FROM {safe_first_table}"),
        ),
        AnalysisPlanStep(
            step_title=f"{first_table} Business Summary",
            purpose="Summarize available business records without analyzing technical identifiers.",
            sql_query=_complete_sql(f"SELECT COUNT(*) AS total_records FROM {safe_first_table}"),
        ),
        AnalysisPlanStep(
            step_title=f"{second_table} Volume",
            purpose="Compare business volume across another table when present.",
            sql_query=_complete_sql(f"SELECT COUNT(*) AS total_records FROM {safe_second_table}"),
        ),
    ]

    if text_column and numeric_column:
        safe_text = _quote_identifier(text_column, db_type)
        safe_numeric = _quote_identifier(numeric_column, db_type)
        steps[1] = AnalysisPlanStep(
            step_title=f"{numeric_column} by {text_column}",
            purpose="Summarize the first available numeric metric by category.",
            sql_query=_complete_sql(
                f"SELECT {safe_text}, AVG({safe_numeric}) AS avg_{numeric_column} "
                f"FROM {safe_first_table} GROUP BY {safe_text} "
                f"ORDER BY avg_{numeric_column} DESC"
            ),
        )
    elif numeric_column:
        safe_numeric = _quote_identifier(numeric_column, db_type)
        steps[1] = AnalysisPlanStep(
            step_title=f"{numeric_column} Summary",
            purpose="Summarize the first available numeric metric.",
            sql_query=_complete_sql(
                f"SELECT AVG({safe_numeric}) AS avg_{numeric_column}, "
                f"MIN({safe_numeric}) AS min_{numeric_column}, "
                f"MAX({safe_numeric}) AS max_{numeric_column} "
                f"FROM {safe_first_table}"
            ),
        )

    return steps


@dataclass(frozen=True)
class AnalysisColumn:
    table: str
    name: str
    type: str
    primary_key: bool = False


@dataclass(frozen=True)
class TableProfile:
    name: str
    columns: list[AnalysisColumn]
    business_numeric_columns: list[str]
    technical_columns: list[str]
    category_columns: list[str]
    date_columns: list[str]
    foreign_key_columns: list[str]
    score: int


@dataclass(frozen=True)
class Relationship:
    fact_table: str
    fact_column: str
    dimension_table: str
    dimension_column: str


@dataclass(frozen=True)
class SchemaAnalysisProfile:
    fact_tables: list[TableProfile]
    dimension_tables: list[TableProfile]
    relationships: list[Relationship]
    all_tables: list[TableProfile]

    def to_prompt_context(self) -> str:
        return json.dumps(
            {
                "fact_tables": [
                    {
                        "name": table.name,
                        "business_numeric_columns": table.business_numeric_columns,
                        "category_columns": table.category_columns,
                        "date_columns": table.date_columns,
                        "foreign_key_columns": table.foreign_key_columns,
                    }
                    for table in self.fact_tables
                ],
                "dimension_tables": [
                    {
                        "name": table.name,
                        "category_columns": table.category_columns,
                        "technical_columns": table.technical_columns,
                    }
                    for table in self.dimension_tables
                ],
                "relationships": [
                    {
                        "fact_table": relation.fact_table,
                        "fact_column": relation.fact_column,
                        "dimension_table": relation.dimension_table,
                        "dimension_column": relation.dimension_column,
                    }
                    for relation in self.relationships
                ],
                "avoid_as_metrics": sorted(_TECHNICAL_FIELD_NAMES),
            },
            indent=2,
        )


def inspect_schema_for_analysis(schema: dict[str, Any]) -> SchemaAnalysisProfile:
    tables_payload = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables_payload, list):
        tables_payload = []
    table_profiles = [
        _profile_table(table)
        for table in tables_payload
        if isinstance(table, dict)
    ]
    relationships = _infer_relationships(table_profiles)
    relationship_fact_names = {relation.fact_table for relation in relationships}
    relationship_dimension_names = {relation.dimension_table for relation in relationships}
    fact_tables = sorted(
        [
            table
            for table in table_profiles
            if table.score > 0 or table.name in relationship_fact_names
        ],
        key=lambda table: table.score + (3 if table.name in relationship_fact_names else 0),
        reverse=True,
    )
    dimension_tables = [
        table
        for table in table_profiles
        if table.name in relationship_dimension_names or table not in fact_tables
    ]
    return SchemaAnalysisProfile(
        fact_tables=fact_tables,
        dimension_tables=dimension_tables,
        relationships=relationships,
        all_tables=table_profiles,
    )


def _business_fallback_steps(
    question: str,
    profile: SchemaAnalysisProfile,
    db_type: str,
) -> list[AnalysisPlanStep]:
    intent = question.lower()
    if _student_intent(intent):
        return _student_fallback_steps(intent, profile, db_type)

    fact = _select_fact_table(profile, intent)
    if fact is None:
        return []

    metric = _select_metric(fact, intent)
    if metric is None:
        return []

    steps: list[AnalysisPlanStep] = []
    region = _find_dimension_column(profile, fact.name, _REGION_COLUMN_NAMES)
    product = _find_dimension_column(profile, fact.name, _PRODUCT_COLUMN_NAMES)
    category = _find_dimension_column(profile, fact.name, _CATEGORY_COLUMN_NAMES)
    segment = _find_dimension_column(profile, fact.name, _SEGMENT_COLUMN_NAMES)
    quantity = _first_matching(fact.business_numeric_columns, _QUANTITY_COLUMN_NAMES)
    date_column = _first_matching(fact.date_columns, _DATE_COLUMN_NAMES)

    if region and _sales_intent(intent):
        steps.append(
            _dimension_metric_step(
                "Revenue by Region",
                "Identify regional revenue concentration and underperforming territories.",
                fact,
                metric,
                region,
                alias="total_revenue",
                db_type=db_type,
            )
        )

    if product:
        steps.append(
            _dimension_metric_step(
                "Revenue by Product",
                "Compare product-level revenue contribution and product mix strength.",
                fact,
                metric,
                product,
                alias="total_revenue" if _sales_intent(intent) else f"total_{metric}",
                db_type=db_type,
            )
        )

    if product and quantity:
        steps.append(
            _dimension_metric_step(
                "Top-Selling Products",
                "Find products with the highest sold quantity and demand signal.",
                fact,
                quantity,
                product,
                alias="units_sold",
                db_type=db_type,
            )
        )

    if category:
        steps.append(
            _dimension_metric_step(
                "Category Performance",
                "Compare category-level performance to find opportunities and risks.",
                fact,
                metric,
                category,
                alias="total_revenue" if _sales_intent(intent) else f"total_{metric}",
                db_type=db_type,
            )
        )

    if segment:
        steps.append(
            _dimension_metric_step(
                "Customer Segment Analysis",
                "Understand performance across customer groups and commercial segments.",
                fact,
                metric,
                segment,
                alias="total_revenue" if _sales_intent(intent) else f"total_{metric}",
                db_type=db_type,
            )
        )

    if date_column:
        safe_fact = _quote_identifier(fact.name, db_type)
        safe_date = _quote_identifier(date_column, db_type)
        safe_metric = _quote_identifier(metric, db_type)
        steps.append(
            AnalysisPlanStep(
                step_title="Performance Trend",
                purpose="Identify movement over time and potential momentum risks.",
                sql_query=_complete_sql(
                    f"SELECT {safe_date} AS period, SUM({safe_metric}) AS "
                    f"{'total_revenue' if _sales_intent(intent) else f'total_{metric}'} "
                    f"FROM {safe_fact} GROUP BY {safe_date} ORDER BY {safe_date}"
                ),
            )
        )

    if not steps and fact.category_columns:
        category_column = fact.category_columns[0]
        safe_category = _quote_identifier(category_column, db_type)
        safe_metric = _quote_identifier(metric, db_type)
        safe_fact = _quote_identifier(fact.name, db_type)
        steps.append(
            AnalysisPlanStep(
                step_title=f"{metric.title()} by {category_column.title()}",
                purpose="Compare the main business metric across the strongest available category.",
                sql_query=_complete_sql(
                    f"SELECT {safe_category}, SUM({safe_metric}) AS total_{metric} "
                    f"FROM {safe_fact} GROUP BY {safe_category} ORDER BY total_{metric} DESC"
                ),
            )
        )

    if len(steps) < 3:
        safe_fact = _quote_identifier(fact.name, db_type)
        safe_metric = _quote_identifier(metric, db_type)
        steps.append(
            AnalysisPlanStep(
                step_title="Overall Business Performance",
                purpose="Summarize the primary business metric at an executive level.",
                sql_query=_complete_sql(
                    f"SELECT SUM({safe_metric}) AS total_{metric}, "
                    f"AVG({safe_metric}) AS average_{metric} FROM {safe_fact}"
                ),
            )
        )

    return steps[:5]


def _student_fallback_steps(
    intent: str,
    profile: SchemaAnalysisProfile,
    db_type: str,
) -> list[AnalysisPlanStep]:
    fact = _select_fact_table(profile, intent)
    if fact is None:
        return _student_schema_gap_steps(profile, db_type)

    marks_metric = _first_matching(fact.business_numeric_columns, _STUDENT_MARKS_COLUMN_NAMES)
    attendance_metric = _first_matching(
        fact.business_numeric_columns,
        _STUDENT_ATTENDANCE_COLUMN_NAMES,
    )
    performance_metric = marks_metric or _first_matching(
        fact.business_numeric_columns,
        _STUDENT_PERFORMANCE_COLUMN_NAMES,
    )
    category_column = _first_matching(fact.category_columns, _STUDENT_GROUP_COLUMN_NAMES)
    student_name_column = _first_matching(fact.category_columns, _STUDENT_NAME_COLUMN_NAMES)

    if not (performance_metric or attendance_metric):
        return _student_schema_gap_steps(profile, db_type)

    safe_fact = _quote_identifier(fact.name, db_type)
    steps: list[AnalysisPlanStep] = []

    if category_column and performance_metric:
        safe_category = _quote_identifier(category_column, db_type)
        safe_metric = _quote_identifier(performance_metric, db_type)
        steps.append(
            AnalysisPlanStep(
                step_title=f"Average {performance_metric.title()} by {category_column.title()}",
                purpose=(
                    "Compare academic performance across student groups to identify strong "
                    "and weak cohorts."
                ),
                sql_query=_complete_sql(
                    f"SELECT {safe_category} AS {category_column}, "
                    f"AVG({safe_metric}) AS avg_{performance_metric}, "
                    f"COUNT(*) AS student_count FROM {safe_fact} "
                    f"GROUP BY {safe_category} ORDER BY avg_{performance_metric} DESC"
                ),
            )
        )

    if category_column and attendance_metric:
        safe_category = _quote_identifier(category_column, db_type)
        safe_attendance = _quote_identifier(attendance_metric, db_type)
        steps.append(
            AnalysisPlanStep(
                step_title=f"Average Attendance by {category_column.title()}",
                purpose=(
                    "Understand attendance consistency across student groups and spot "
                    "engagement risk."
                ),
                sql_query=_complete_sql(
                    f"SELECT {safe_category} AS {category_column}, "
                    f"AVG({safe_attendance}) AS avg_attendance, "
                    f"COUNT(*) AS student_count FROM {safe_fact} "
                    f"GROUP BY {safe_category} ORDER BY avg_attendance DESC"
                ),
            )
        )

    if performance_metric and attendance_metric:
        safe_performance = _quote_identifier(performance_metric, db_type)
        safe_attendance = _quote_identifier(attendance_metric, db_type)
        segment_case = (
            f"CASE WHEN {safe_performance} < 60 OR {safe_attendance} < 75 "
            f"THEN 'Needs Attention' WHEN {safe_performance} >= 80 "
            f"AND {safe_attendance} >= 85 THEN 'High Performing' ELSE 'Stable' END"
        )
        steps.append(
            AnalysisPlanStep(
                step_title="Student Performance Risk Segments",
                purpose=(
                    "Segment students into performance and attendance risk groups for "
                    "executive-level intervention planning."
                ),
                sql_query=_complete_sql(
                    f"SELECT {segment_case} AS performance_segment, "
                    f"COUNT(*) AS student_count, "
                    f"AVG({safe_performance}) AS avg_{performance_metric}, "
                    f"AVG({safe_attendance}) AS avg_attendance FROM {safe_fact} "
                    f"GROUP BY {segment_case} ORDER BY student_count DESC"
                ),
            )
        )

    if student_name_column and performance_metric:
        safe_name = _quote_identifier(student_name_column, db_type)
        safe_performance = _quote_identifier(performance_metric, db_type)
        selected_columns = [
            f"{safe_name} AS {student_name_column}",
            f"{safe_performance} AS {performance_metric}",
        ]
        if attendance_metric:
            selected_columns.append(
                f"{_quote_identifier(attendance_metric, db_type)} AS {attendance_metric}"
            )
        steps.append(
            AnalysisPlanStep(
                step_title="Top Student Performance",
                purpose="Identify the strongest individual performers for benchmarking.",
                sql_query=_complete_sql(
                    f"SELECT {', '.join(selected_columns)} FROM {safe_fact} "
                    f"ORDER BY {safe_performance} DESC"
                ),
            )
        )

    aggregate_parts = ["COUNT(*) AS student_count"]
    if performance_metric:
        safe_performance = _quote_identifier(performance_metric, db_type)
        aggregate_parts.append(f"AVG({safe_performance}) AS avg_{performance_metric}")
    if attendance_metric:
        safe_attendance = _quote_identifier(attendance_metric, db_type)
        aggregate_parts.append(f"AVG({safe_attendance}) AS avg_attendance")
    steps.append(
        AnalysisPlanStep(
            step_title="Overall Student Performance",
            purpose="Summarize the core student performance indicators for the request.",
            sql_query=_complete_sql(f"SELECT {', '.join(aggregate_parts)} FROM {safe_fact}"),
        )
    )

    return _dedupe_steps(steps)[:5]


def _student_schema_gap_steps(
    profile: SchemaAnalysisProfile,
    db_type: str,
) -> list[AnalysisPlanStep]:
    first_tables = profile.all_tables[:3]
    if not first_tables:
        return [
            AnalysisPlanStep(
                step_title="Student Performance Schema Gap",
                purpose=(
                    "Explain that student performance analysis cannot run because no tables "
                    "are visible in the connected schema."
                ),
                sql_query=(
                    "SELECT 'No tables found for student performance analysis' "
                    "AS analysis_note"
                )
                + ";",
            ),
            AnalysisPlanStep(
                step_title="Required Student Metrics",
                purpose=(
                    "Identify the columns needed for a meaningful student performance "
                    "analysis."
                ),
                sql_query=(
                    "SELECT 'Expected columns include marks, score, attendance, course, "
                    "branch, or student name' AS analysis_note"
                )
                + ";",
            ),
            AnalysisPlanStep(
                step_title="Next Step",
                purpose="Recommend connecting a student or academic performance database.",
                sql_query=(
                    "SELECT 'Connect a database containing student marks and attendance' "
                    "AS analysis_note"
                )
                + ";",
            ),
        ]

    steps = [
        AnalysisPlanStep(
            step_title=f"Student Performance Schema Coverage: {table.name}",
            purpose=(
                "Check available records while noting that this table does not expose clear "
                "student performance metrics."
            ),
            sql_query=_complete_sql(
                "SELECT COUNT(*) AS available_records "
                f"FROM {_quote_identifier(table.name, db_type)}"
            ),
        )
        for table in first_tables
    ]
    while len(steps) < 3:
        steps.append(
            AnalysisPlanStep(
                step_title="Student Performance Schema Gap",
                purpose=(
                    "Explain that marks, attendance, score, branch, or course columns are "
                    "needed for the requested analysis."
                ),
                sql_query=(
                    "SELECT 'Student performance fields were not found in the connected "
                    "schema' AS analysis_note"
                )
                + ";",
            )
        )
    return steps[:3]


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


def _normalize_steps_for_db(
    steps: list[AnalysisPlanStep],
    schema: dict[str, Any],
    db_type: str,
) -> list[AnalysisPlanStep]:
    return [
        AnalysisPlanStep(
            step_title=step.step_title,
            purpose=step.purpose,
            sql_query=_normalize_sql_for_db(step.sql_query, schema, db_type),
        )
        for step in steps
    ]


def _normalize_sql_for_db(sql: str, schema: dict[str, Any], db_type: str) -> str:
    cleaned = sql.strip().rstrip(";")
    quote = _identifier_quote(db_type)
    alternate_quote = '"' if quote == "`" else "`"
    identifiers = _schema_identifiers(schema)

    for identifier in sorted(identifiers, key=len, reverse=True):
        escaped_for_quote = _escape_identifier(identifier, quote)
        escaped_for_alternate = _escape_identifier(identifier, alternate_quote)
        cleaned = cleaned.replace(
            f"{alternate_quote}{escaped_for_alternate}{alternate_quote}",
            f"{quote}{escaped_for_quote}{quote}",
        )

    cleaned = _qualify_join_columns(cleaned, schema, db_type)
    return _complete_sql(cleaned)


def _schema_identifiers(schema: dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, list):
        return identifiers
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = table.get("name")
        if isinstance(table_name, str):
            identifiers.add(table_name)
        for column in _table_columns(table):
            column_name = column.get("name")
            if isinstance(column_name, str):
                identifiers.add(column_name)
    return identifiers


def _qualify_join_columns(sql: str, schema: dict[str, Any], db_type: str) -> str:
    if not re.search(r"\bjoin\b", sql, flags=re.IGNORECASE):
        return sql

    joined_tables = _joined_table_references(sql, db_type)
    if len(joined_tables) < 2:
        return sql

    table_columns = _schema_table_columns(schema)
    primary_keys = _schema_primary_keys(schema)
    active_tables = {
        table_name: alias
        for table_name, alias in joined_tables.items()
        if table_name in table_columns
    }
    if len(active_tables) < 2:
        return sql

    protected_aliases = _sql_output_aliases(sql, db_type)
    column_owner: dict[str, str] = {}
    all_columns = sorted(
        {column for table in active_tables for column in table_columns.get(table, set())},
        key=len,
        reverse=True,
    )
    for column in all_columns:
        owners = [table for table in active_tables if column in table_columns.get(table, set())]
        if not owners:
            continue
        column_owner[column] = _preferred_column_owner(column, owners, primary_keys)

    qualified = sql
    for column, table_name in column_owner.items():
        if column in protected_aliases:
            continue
        owner_ref = active_tables[table_name]
        qualifier = _quote_identifier(owner_ref, db_type)
        qualified_column = f"{qualifier}.{_quote_identifier(column, db_type)}"
        quoted_column = _quote_identifier(column, db_type)
        qualified = _replace_unqualified_identifier(
            qualified,
            quoted_column,
            qualified_column,
            quoted=True,
        )
        qualified = _replace_unqualified_identifier(
            qualified,
            column,
            qualified_column,
            quoted=False,
        )

    return qualified


def _replace_unqualified_identifier(
    sql: str,
    identifier: str,
    replacement: str,
    *,
    quoted: bool,
) -> str:
    pattern = re.escape(identifier) if quoted else rf"\b{re.escape(identifier)}\b"

    def replace_match(match: re.Match[str]) -> str:
        start, end = match.span()
        before = sql[:start]
        after = sql[end:]
        if _is_qualified_reference_context(before, after):
            return match.group(0)
        if _is_alias_declaration_context(before):
            return match.group(0)
        if not quoted and _is_inside_quoted_identifier_context(before, after):
            return match.group(0)
        return replacement

    return re.sub(pattern, replace_match, sql, flags=0 if quoted else re.IGNORECASE)


def _is_qualified_reference_context(before: str, after: str) -> bool:
    return before.rstrip().endswith(".") or after.lstrip().startswith(".")


def _is_alias_declaration_context(before: str) -> bool:
    return re.search(r"\bas\s+$", before, flags=re.IGNORECASE) is not None


def _is_inside_quoted_identifier_context(before: str, after: str) -> bool:
    return (
        bool(before) and before[-1] in {'"', "`"}
    ) or (
        bool(after) and after[0] in {'"', "`"}
    )


def _sql_output_aliases(sql: str, db_type: str) -> set[str]:
    quote = re.escape(_identifier_quote(db_type))
    alias_pattern = re.compile(
        rf"\bas\s+(?:{quote}(?P<quoted>[^`\"]+){quote}|(?P<bare>[A-Za-z_][\w]*))",
        flags=re.IGNORECASE,
    )
    return {
        alias
        for match in alias_pattern.finditer(sql)
        for alias in (match.group("quoted") or match.group("bare"),)
        if alias
    }


def _joined_table_references(sql: str, db_type: str) -> dict[str, str]:
    quote = re.escape(_identifier_quote(db_type))
    table_pattern = rf"{quote}(?P<quoted>[^`\"]+){quote}|(?P<bare>[A-Za-z_][\w]*)"
    reserved_words = (
        "join|on|where|group|order|limit|left|right|inner|outer|full|cross|having"
    )
    relation_pattern = re.compile(
        rf"\b(?:from|join)\s+(?P<table>{table_pattern})"
        rf"(?:\s+(?:as\s+)?(?P<alias>(?!(?:{reserved_words})\b)[A-Za-z_][\w]*))?",
        flags=re.IGNORECASE,
    )
    references: dict[str, str] = {}
    for match in relation_pattern.finditer(sql):
        table_name = match.group("quoted") or match.group("bare")
        alias = match.group("alias")
        references[table_name] = alias or table_name
    return references


def _schema_table_columns(schema: dict[str, Any]) -> dict[str, set[str]]:
    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, list):
        return {}
    table_columns: dict[str, set[str]] = {}
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = table.get("name")
        if not isinstance(table_name, str):
            continue
        table_columns[table_name] = {
            str(column["name"])
            for column in _table_columns(table)
            if isinstance(column.get("name"), str)
        }
    return table_columns


def _schema_primary_keys(schema: dict[str, Any]) -> dict[str, set[str]]:
    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, list):
        return {}
    primary_keys: dict[str, set[str]] = {}
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = table.get("name")
        if not isinstance(table_name, str):
            continue
        primary_keys[table_name] = {
            str(column["name"])
            for column in _table_columns(table)
            if isinstance(column.get("name"), str) and bool(column.get("primary_key", False))
        }
    return primary_keys


def _preferred_column_owner(
    column: str,
    owners: list[str],
    primary_keys: dict[str, set[str]],
) -> str:
    primary_key_owners = [table for table in owners if column in primary_keys.get(table, set())]
    if primary_key_owners:
        return primary_key_owners[0]
    return owners[0]


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


_TECHNICAL_FIELD_NAMES = {
    "id",
    "customer_id",
    "product_id",
    "order_id",
    "student_id",
    "user_id",
    "created_by",
    "updated_by",
}
_BUSINESS_METRIC_NAMES = {
    "revenue",
    "sales",
    "sale",
    "amount",
    "total",
    "total_amount",
    "price",
    "quantity",
    "qty",
    "attendance",
    "marks",
    "mark",
    "score",
    "performance",
    "rating",
    "profit",
    "cost",
}
_FACT_TABLE_HINTS = {
    "sales",
    "sale",
    "orders",
    "order",
    "order_items",
    "transactions",
    "attendance",
    "marks",
    "scores",
    "performance",
    "enrollments",
}
_REGION_COLUMN_NAMES = {"region", "state", "country", "city", "territory", "zone", "location"}
_PRODUCT_COLUMN_NAMES = {"product", "product_name", "name", "item", "item_name", "sku"}
_CATEGORY_COLUMN_NAMES = {"category", "product_category", "type", "class"}
_SEGMENT_COLUMN_NAMES = {"segment", "customer_segment", "tier", "customer_type"}
_QUANTITY_COLUMN_NAMES = {"quantity", "qty", "units", "units_sold", "count"}
_DATE_COLUMN_NAMES = {"date", "order_date", "created_at", "sale_date", "transaction_date", "month"}
_STUDENT_INTENT_TERMS = {
    "student",
    "students",
    "academic",
    "marks",
    "mark",
    "score",
    "attendance",
    "course",
    "branch",
    "grade",
    "class",
}
_STUDENT_MARKS_COLUMN_NAMES = {"marks", "mark", "score", "scores", "grade", "performance"}
_STUDENT_ATTENDANCE_COLUMN_NAMES = {"attendance", "attended", "attendance_rate"}
_STUDENT_PERFORMANCE_COLUMN_NAMES = {
    "marks",
    "mark",
    "score",
    "scores",
    "grade",
    "performance",
    "attendance",
}
_STUDENT_GROUP_COLUMN_NAMES = {
    "branch",
    "course",
    "class",
    "section",
    "department",
    "program",
    "semester",
}
_STUDENT_NAME_COLUMN_NAMES = {"student", "student_name", "name", "full_name"}
_SALES_DOMAIN_TERMS = {
    "revenue",
    "sales",
    "sale",
    "product",
    "products",
    "selling",
    "customer",
    "customers",
    "segment",
    "commercial",
}
_TECHNICAL_AGGREGATE_PATTERN = re.compile(
    r"\b(avg|sum|min|max)\s*\(\s*\"?([a-zA-Z_][\w]*)\"?\s*\)",
    re.IGNORECASE,
)


def _profile_table(table: dict[str, Any]) -> TableProfile:
    table_name = _table_name(table)
    raw_columns = _table_columns(table)
    columns = [
        AnalysisColumn(
            table=table_name,
            name=str(column.get("name", "")),
            type=str(column.get("type", "")),
            primary_key=bool(column.get("primary_key", False)),
        )
        for column in raw_columns
        if column.get("name")
    ]
    business_numeric = [
        column.name
        for column in columns
        if _is_numeric_type(column.type)
        and not _is_technical_column(column.name)
        and _looks_like_business_metric(column.name)
    ]
    category_columns = [
        column.name
        for column in columns
        if _is_text_type(column.type) and not _is_technical_column(column.name)
    ]
    date_columns = [
        column.name
        for column in columns
        if _is_date_type(column.type)
        or any(token in column.name.lower() for token in _DATE_COLUMN_NAMES)
    ]
    foreign_keys = [
        column.name
        for column in columns
        if column.name.lower().endswith("_id") and not column.primary_key
    ]
    technical_columns = [
        column.name
        for column in columns
        if _is_technical_column(column.name) or column.primary_key
    ]
    table_name_lower = table_name.lower()
    score = len(business_numeric) * 4 + len(foreign_keys) * 2 + len(date_columns)
    if any(hint in table_name_lower for hint in _FACT_TABLE_HINTS):
        score += 4
    return TableProfile(
        name=table_name,
        columns=columns,
        business_numeric_columns=business_numeric,
        technical_columns=technical_columns,
        category_columns=category_columns,
        date_columns=date_columns,
        foreign_key_columns=foreign_keys,
        score=score,
    )


def _infer_relationships(tables: list[TableProfile]) -> list[Relationship]:
    relationships: list[Relationship] = []
    table_by_name = {table.name.lower(): table for table in tables}
    for fact in tables:
        for fk_column in fact.foreign_key_columns:
            stem = fk_column.lower().removesuffix("_id")
            dimension = (
                table_by_name.get(stem)
                or table_by_name.get(f"{stem}s")
                or table_by_name.get(stem.rstrip("s"))
            )
            if dimension is None or dimension.name == fact.name:
                continue
            dimension_key = _dimension_key_column(dimension, stem)
            if dimension_key:
                relationships.append(
                    Relationship(
                        fact_table=fact.name,
                        fact_column=fk_column,
                        dimension_table=dimension.name,
                        dimension_column=dimension_key,
                    )
                )
    return relationships


def _dimension_key_column(table: TableProfile, stem: str) -> str | None:
    candidates = [f"{stem}_id", "id", f"{table.name.rstrip('s')}_id"]
    for candidate in candidates:
        for column in table.columns:
            if column.name.lower() == candidate.lower():
                return column.name
    for column in table.columns:
        if column.primary_key:
            return column.name
    return None


def _contains_low_value_technical_analysis(
    steps: list[AnalysisPlanStep],
    question: str,
) -> bool:
    if _explicit_identifier_request(question):
        return False
    for step in steps:
        text = f"{step.step_title} {step.purpose} {step.sql_query}".lower()
        if "average id" in text or "avg id" in text or "min id" in text or "max id" in text:
            return True
        for match in _TECHNICAL_AGGREGATE_PATTERN.finditer(step.sql_query):
            if _is_technical_column(match.group(2)):
                return True
    return False


def _contains_intent_mismatch(steps: list[AnalysisPlanStep], question: str) -> bool:
    text = " ".join(
        f"{step.step_title} {step.purpose} {step.sql_query}"
        for step in steps
    ).lower()
    question_text = question.lower()
    if _student_intent(question_text):
        return any(term in text for term in _SALES_DOMAIN_TERMS) and not any(
            term in text for term in _STUDENT_INTENT_TERMS
        )
    if _sales_intent(question_text):
        return "student" in text and not any(term in text for term in _SALES_DOMAIN_TERMS)
    return False


def _select_fact_table(profile: SchemaAnalysisProfile, intent: str) -> TableProfile | None:
    if not profile.fact_tables:
        return None
    if _student_intent(intent):
        student_tables = sorted(
            [
                table
                for table in profile.fact_tables
                if _table_matches_student_intent(table)
            ],
            key=lambda table: _student_table_score(table),
            reverse=True,
        )
        if student_tables:
            return student_tables[0]
    if _sales_intent(intent):
        for table in profile.fact_tables:
            if any(token in table.name.lower() for token in ("sale", "order", "transaction")):
                return table
    return profile.fact_tables[0]


def _select_metric(table: TableProfile, intent: str) -> str | None:
    if _sales_intent(intent):
        preferred = (
            "revenue",
            "total_revenue",
            "sales",
            "total_sales",
            "total_amount",
            "amount",
            "price",
        )
        metric = _first_matching(table.business_numeric_columns, set(preferred))
        if metric:
            return metric
    for preferred in ("marks", "score", "attendance", "performance", "quantity", "amount"):
        metric = _first_matching(table.business_numeric_columns, {preferred})
        if metric:
            return metric
    return table.business_numeric_columns[0] if table.business_numeric_columns else None


def _find_dimension_column(
    profile: SchemaAnalysisProfile,
    fact_table: str,
    column_names: set[str],
) -> tuple[str, str, Relationship | None] | None:
    fact = next((table for table in profile.all_tables if table.name == fact_table), None)
    if fact:
        direct = _first_matching(fact.category_columns, column_names)
        if direct:
            return fact.name, direct, None

    for relation in profile.relationships:
        if relation.fact_table != fact_table:
            continue
        dimension = next(
            (table for table in profile.all_tables if table.name == relation.dimension_table),
            None,
        )
        if dimension is None:
            continue
        dimension_column = _first_matching(dimension.category_columns, column_names)
        if dimension_column:
            return dimension.name, dimension_column, relation
    return None


def _dimension_metric_step(
    title: str,
    purpose: str,
    fact: TableProfile,
    metric: str,
    dimension_ref: tuple[str, str, Relationship | None],
    *,
    alias: str,
    db_type: str,
) -> AnalysisPlanStep:
    dimension_table, dimension_column, relation = dimension_ref
    safe_metric = _quote_identifier(metric, db_type)
    if relation is None:
        safe_fact = _quote_identifier(fact.name, db_type)
        safe_dimension = _quote_identifier(dimension_column, db_type)
        sql = _complete_sql(
            f"SELECT {safe_dimension} AS {dimension_column}, SUM({safe_metric}) AS {alias} "
            f"FROM {safe_fact} GROUP BY {safe_dimension} ORDER BY {alias} DESC"
        )
    else:
        fact_alias = "f"
        dimension_alias = "d"
        safe_dimension_column = _quote_identifier(dimension_column, db_type)
        sql = _complete_sql(
            f"SELECT {dimension_alias}.{safe_dimension_column} AS {dimension_column}, "
            f"SUM({fact_alias}.{safe_metric}) AS {alias} "
            f"FROM {_quote_identifier(fact.name, db_type)} {fact_alias} "
            f"JOIN {_quote_identifier(dimension_table, db_type)} {dimension_alias} "
            f"ON {fact_alias}.{_quote_identifier(relation.fact_column, db_type)} = "
            f"{dimension_alias}.{_quote_identifier(relation.dimension_column, db_type)} "
            f"GROUP BY {dimension_alias}.{safe_dimension_column} "
            f"ORDER BY {alias} DESC"
        )
    return AnalysisPlanStep(step_title=title, purpose=purpose, sql_query=sql)


def _first_matching(columns: list[str], preferred_names: set[str]) -> str | None:
    for column in columns:
        column_lower = column.lower()
        if column_lower in preferred_names:
            return column
    for column in columns:
        column_lower = column.lower()
        if any(name in column_lower for name in preferred_names):
            return column
    return None


def _sales_intent(intent: str) -> bool:
    return any(token in intent for token in ("sale", "sales", "revenue", "order", "product"))


def _student_intent(intent: str) -> bool:
    return any(token in intent for token in _STUDENT_INTENT_TERMS)


def _table_matches_student_intent(table: TableProfile) -> bool:
    searchable = " ".join(
        [table.name]
        + table.business_numeric_columns
        + table.category_columns
        + table.technical_columns
    ).lower()
    return any(token in searchable for token in _STUDENT_INTENT_TERMS)


def _student_table_score(table: TableProfile) -> int:
    score = 0
    searchable = " ".join(
        [table.name]
        + table.business_numeric_columns
        + table.category_columns
        + table.technical_columns
    ).lower()
    for token in _STUDENT_INTENT_TERMS:
        if token in searchable:
            score += 2
    for metric in _STUDENT_PERFORMANCE_COLUMN_NAMES:
        if any(metric in column.lower() for column in table.business_numeric_columns):
            score += 4
    for group in _STUDENT_GROUP_COLUMN_NAMES:
        if any(group in column.lower() for column in table.category_columns):
            score += 2
    return score


def _explicit_identifier_request(question: str) -> bool:
    text = question.lower()
    return " id" in text or "identifier" in text or "primary key" in text


def _is_technical_column(column_name: str) -> bool:
    lowered = column_name.lower()
    return lowered in _TECHNICAL_FIELD_NAMES or lowered.endswith("_id")


def _looks_like_business_metric(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(token in lowered for token in _BUSINESS_METRIC_NAMES)


def _is_numeric_type(column_type: str) -> bool:
    lowered = column_type.lower()
    return any(
        fragment in lowered
        for fragment in ("int", "real", "numeric", "decimal", "double", "float")
    )


def _is_text_type(column_type: str) -> bool:
    lowered = column_type.lower()
    return any(fragment in lowered for fragment in ("text", "char", "varchar", "string"))


def _is_date_type(column_type: str) -> bool:
    lowered = column_type.lower()
    return any(fragment in lowered for fragment in ("date", "time", "timestamp"))


def _first_column_by_type(
    columns: list[dict[str, Any]],
    type_fragments: tuple[str, ...],
) -> str | None:
    for column in columns:
        column_type = str(column.get("type", "")).lower()
        if any(fragment in column_type for fragment in type_fragments):
            return str(column.get("name"))
    return None


def _first_business_numeric_column(
    columns: list[dict[str, Any]],
    type_fragments: tuple[str, ...],
) -> str | None:
    for column in columns:
        column_name = str(column.get("name", ""))
        column_type = str(column.get("type", "")).lower()
        if _is_technical_column(column_name):
            continue
        if any(fragment in column_type for fragment in type_fragments):
            return column_name
    return None


def _dialect_prompt_context(db_type: str) -> str:
    quote = _identifier_quote(db_type)
    if quote == "`":
        return (
            "Database type: mysql. Quote identifiers with backticks, for example "
            "`table_name` and `column_name`. Do not use double quotes for identifiers. "
            "End each sql_query with a semicolon."
        )
    return (
        f"Database type: {db_type or 'sqlite'}. Quote identifiers with double quotes, "
        'for example "table_name" and "column_name". End each sql_query with a semicolon.'
    )


def _quote_identifier(identifier: str, db_type: str = "sqlite") -> str:
    quote = _identifier_quote(db_type)
    return quote + _escape_identifier(identifier, quote) + quote


def _identifier_quote(db_type: str) -> str:
    return "`" if db_type.lower() == "mysql" else '"'


def _escape_identifier(identifier: str, quote: str) -> str:
    return identifier.replace(quote, quote * 2)


def _complete_sql(sql: str) -> str:
    return sql.strip().rstrip(";") + ";"


def _dedupe_steps(steps: list[AnalysisPlanStep]) -> list[AnalysisPlanStep]:
    seen_sql: set[str] = set()
    deduped: list[AnalysisPlanStep] = []
    for step in steps:
        normalized_sql = " ".join(step.sql_query.lower().split())
        if normalized_sql in seen_sql:
            continue
        seen_sql.add(normalized_sql)
        deduped.append(step)
    return deduped
