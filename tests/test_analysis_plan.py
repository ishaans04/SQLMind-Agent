import json

import httpx
import pytest

from sqlmind_agent.analysis_plan import (
    ANALYSIS_PLAN_SYSTEM_PROMPT,
    FINAL_REPORT_SYSTEM_PROMPT,
    AnalysisPlanner,
    _parse_json_object,
    fallback_analysis_plan,
    inspect_schema_for_analysis,
)
from sqlmind_agent.nim_client import NIMClient
from sqlmind_agent.schemas import ExecutedAnalysisStep, QueryResults


def test_generate_plan_from_mocked_nim_response(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            requests.append(json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": """
                                {
                                  "steps": [
                                    {
                                      "step_title": "Average marks",
                                      "purpose": "Measure performance.",
                                      "sql_query": "SELECT AVG(score) AS avg_score FROM marks"
                                    },
                                    {
                                      "step_title": "Marks by course",
                                      "purpose": "Compare courses.",
                                      "sql_query": "SELECT course_id, score FROM marks"
                                    },
                                    {
                                      "step_title": "Attendance",
                                      "purpose": "Review attendance.",
                                      "sql_query": "SELECT student_id, attended FROM attendance"
                                    }
                                  ]
                                }
                                """
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    planner = AnalysisPlanner(NIMClient(api_key="test-key"))
    steps = planner.generate_plan("Analyze student performance", {"tables": []})

    assert len(steps) == 3
    assert steps[0].step_title == "Average marks"
    assert steps[0].sql_query.startswith("SELECT")
    assert "3 to 5" in requests[0]["messages"][0]["content"]
    assert "Schema business profile" in requests[0]["messages"][1]["content"]


def test_analysis_prompt_requires_business_metrics_and_avoids_technical_fields() -> None:
    assert "senior business analyst" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "fact tables" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "dimension tables" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "multi-query investigation" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "distinct" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "sub-question" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "subqueries or CTEs" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "Use joins whenever relationships exist" in ANALYSIS_PLAN_SYSTEM_PROMPT
    assert "Never analyze technical identifier fields" in ANALYSIS_PLAN_SYSTEM_PROMPT


def test_final_report_from_mocked_nim_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"choices": [{"message": {"content": "Performance is strong overall."}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    step = ExecutedAnalysisStep(
        step_title="Average marks",
        purpose="Measure performance.",
        sql_query="SELECT AVG(score) AS avg_score FROM marks",
        success=True,
        results=QueryResults(columns=["avg_score"], rows=[{"avg_score": 82}], row_count=1),
    )
    report = AnalysisPlanner(NIMClient(api_key="test-key")).final_report(
        "Analyze student performance",
        [step],
    )

    assert report == "Performance is strong overall."


def test_smart_analysis_report_prompt_requires_structured_markdown() -> None:
    assert "# Smart Analysis Report" in FINAL_REPORT_SYSTEM_PROMPT
    assert "## Executive Summary" in FINAL_REPORT_SYSTEM_PROMPT
    assert "## Key Findings" in FINAL_REPORT_SYSTEM_PROMPT
    assert "## Supporting Metrics" in FINAL_REPORT_SYSTEM_PROMPT
    assert "## Recommendations" in FINAL_REPORT_SYSTEM_PROMPT
    assert "## Attention Areas" in FINAL_REPORT_SYSTEM_PROMPT
    assert "Return clean Markdown only" in FINAL_REPORT_SYSTEM_PROMPT
    assert "Do not include JSON" in FINAL_REPORT_SYSTEM_PROMPT
    assert "every successful executed SQL step" in FINAL_REPORT_SYSTEM_PROMPT
    assert "Query-by-Query Findings" in FINAL_REPORT_SYSTEM_PROMPT


def test_parse_json_object_accepts_code_fence() -> None:
    payload = _parse_json_object('```json\n{"steps": []}\n```')

    assert payload == {"steps": []}


def test_parse_json_object_accepts_valid_json() -> None:
    payload = _parse_json_object('{"steps": []}')

    assert payload == {"steps": []}


def test_parse_json_object_accepts_leading_and_trailing_text() -> None:
    payload = _parse_json_object('Here is the plan:\n{"steps": []}\nHope this helps.')

    assert payload == {"steps": []}


def test_generate_plan_falls_back_when_nim_json_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"choices": [{"message": {"content": "not valid json"}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    schema = _sales_schema()
    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze sales performance across products and regions",
        schema,
    )

    sql = "\n".join(step.sql_query for step in steps)
    titles = [step.step_title for step in steps]
    assert len(steps) >= 3
    assert "Revenue by Region" in titles
    assert "Revenue by Product" in titles
    assert "Top-Selling Products" in titles
    assert "JOIN" in sql
    assert "SUM" in sql
    assert "AVG(\"id\")" not in sql
    assert "MIN(\"id\")" not in sql
    assert "MAX(\"id\")" not in sql


def test_schema_profile_identifies_fact_dimensions_and_relationships() -> None:
    profile = inspect_schema_for_analysis(_sales_schema())

    assert profile.fact_tables[0].name == "orders"
    assert {relation.dimension_table for relation in profile.relationships} == {
        "customers",
        "products",
    }
    assert "total_amount" in profile.fact_tables[0].business_numeric_columns
    assert "order_id" in profile.fact_tables[0].technical_columns


def test_fallback_sales_plan_uses_business_joins_not_identifier_metrics() -> None:
    steps = fallback_analysis_plan(
        "Analyze sales performance across products and regions",
        _sales_schema(),
    )

    sql = "\n".join(step.sql_query for step in steps)
    assert any(step.step_title == "Revenue by Region" for step in steps)
    assert any(step.step_title == "Revenue by Product" for step in steps)
    assert "JOIN \"customers\"" in sql
    assert "JOIN \"products\"" in sql
    assert "SUM(f.\"total_amount\")" in sql
    assert "AVG(\"order_id\")" not in sql
    assert "AVG(\"customer_id\")" not in sql


def test_fallback_sales_plan_uses_mysql_backticks_and_semicolons() -> None:
    steps = fallback_analysis_plan(
        "Analyze sales performance across products and regions",
        _sales_schema(),
        db_type="mysql",
    )

    sql = "\n".join(step.sql_query for step in steps)
    assert "JOIN `customers`" in sql
    assert "JOIN `products`" in sql
    assert "SUM(f.`total_amount`)" in sql
    assert '"customers"' not in sql
    assert '"products"' not in sql
    assert all(step.sql_query.endswith(";") for step in steps)


def test_fallback_student_plan_uses_student_metrics_not_sales_widgets() -> None:
    steps = fallback_analysis_plan(
        "analyze student performance",
        _student_schema(),
    )

    titles = [step.step_title for step in steps]
    sql = "\n".join(step.sql_query for step in steps)
    assert any("Marks" in title or "Score" in title for title in titles)
    assert any("Attendance" in title for title in titles)
    assert any("Risk" in title for title in titles)
    assert "Revenue by Product" not in titles
    assert "Top-Selling Products" not in titles
    assert "SUM(f.\"total_amount\")" not in sql
    assert "\"marks\"" in sql
    assert "\"attendance\"" in sql


def test_student_prompt_with_sales_schema_reports_schema_gap_not_sales_plan() -> None:
    steps = fallback_analysis_plan(
        "analyze student performance",
        _sales_schema(),
    )

    titles = [step.step_title for step in steps]
    assert all(
        "Student Performance" in title or "Required Student Metrics" in title
        for title in titles
    )
    assert "Revenue by Product" not in titles
    assert "Top-Selling Products" not in titles
    assert all("total_amount" not in step.sql_query for step in steps)


def test_generate_plan_replaces_low_value_nim_identifier_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": """
                                {
                                  "steps": [
                                    {
                                      "step_title": "Average order id",
                                      "purpose": "Find average id.",
                                      "sql_query": "SELECT AVG(id) AS avg_id FROM orders"
                                    },
                                    {
                                      "step_title": "Min order id",
                                      "purpose": "Find min id.",
                                      "sql_query": "SELECT MIN(id) AS min_id FROM orders"
                                    },
                                    {
                                      "step_title": "Max order id",
                                      "purpose": "Find max id.",
                                      "sql_query": "SELECT MAX(id) AS max_id FROM orders"
                                    }
                                  ]
                                }
                                """
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze sales performance across products and regions",
        _sales_schema(),
    )

    assert steps[0].step_title == "Revenue by Region"
    assert all("order_id" not in step.sql_query.lower() for step in steps)


def test_generate_plan_replaces_wrong_domain_sales_plan_for_student_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": """
                                {
                                  "steps": [
                                    {
                                      "step_title": "Revenue by Product",
                                      "purpose": "Compare product-level revenue.",
                                      "sql_query": "SELECT product, SUM(amount) FROM sales"
                                    },
                                    {
                                      "step_title": "Top-Selling Products",
                                      "purpose": "Find strongest products.",
                                      "sql_query": "SELECT product, SUM(quantity) FROM sales"
                                    },
                                    {
                                      "step_title": "Customer Segment Analysis",
                                      "purpose": "Review customer segments.",
                                      "sql_query": "SELECT segment, SUM(amount) FROM sales"
                                    }
                                  ]
                                }
                                """
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "analyze student performance",
        _student_schema(),
    )

    titles = [step.step_title for step in steps]
    assert "Revenue by Product" not in titles
    assert "Top-Selling Products" not in titles
    assert any("Attendance" in title or "Marks" in title for title in titles)


def test_generate_plan_normalizes_nim_double_quotes_for_mysql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": """
                                {
                                  "steps": [
                                    {
                                      "step_title": "Revenue by Region",
                                      "purpose": "Compare regional sales.",
                                      "sql_query": "SELECT \"region\" FROM \"orders\""
                                    },
                                    {
                                      "step_title": "Revenue by Product",
                                      "purpose": "Compare product sales.",
                                      "sql_query": "SELECT \"product_id\" FROM \"orders\""
                                    },
                                    {
                                      "step_title": "Total Revenue",
                                      "purpose": "Measure overall sales.",
                                      "sql_query": "SELECT \"total_amount\" FROM \"orders\""
                                    }
                                  ]
                                }
                                """
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze sales performance",
        _sales_schema(),
        db_type="mysql",
    )

    sql = "\n".join(step.sql_query for step in steps)
    assert "`orders`" in sql
    assert "`total_amount`" in sql
    assert '"orders"' not in sql
    assert '"total_amount"' not in sql
    assert all(step.sql_query.endswith(";") for step in steps)


def test_generate_plan_qualifies_join_columns_for_mysql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            failed_query = (
                "SELECT `product_id`, `product_name`, SUM(`quantity`) as total_quantity "
                "FROM `orders` JOIN `products` "
                "ON `orders`.`product_id` = `products`.`product_id` "
                "GROUP BY `product_id`, `product_name` "
                "ORDER BY total_quantity DESC LIMIT 5"
            )
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json_plan(
                                    [
                                        failed_query,
                                        "SELECT `product_id` FROM `orders`",
                                        "SELECT `total_amount` FROM `orders`",
                                    ]
                                )
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze top selling products",
        _sales_schema(),
        db_type="mysql",
    )

    sql = steps[0].sql_query
    assert "SELECT `products`.`product_id`, `products`.`product_name`" in sql
    assert "SUM(`orders`.`quantity`) as total_quantity" in sql
    assert "GROUP BY `products`.`product_id`, `products`.`product_name`" in sql
    assert "`orders`.`product_id` = `products`.`product_id`" in sql
    assert sql.endswith(";")


def test_generate_plan_does_not_qualify_output_aliases_in_joined_cte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            cte_query = (
                'WITH student_course AS (SELECT s.id AS "student_id", '
                'c.id AS "course_id", m.score AS "score" '
                "FROM students s JOIN marks m ON s.id = m.student_id "
                "JOIN courses c ON m.course_id = c.id) "
                'SELECT "student_id", "course_id", AVG("score") AS average_score '
                'FROM student_course GROUP BY "student_id", "course_id"'
            )
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"choices": [{"message": {"content": json_plan([cte_query] * 3)}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze student performance by course",
        _student_join_schema(),
    )

    sql = steps[0].sql_query
    assert 'AS "student_id"' in sql
    assert 'AS "course_id"' in sql
    assert 'AS "score"' in sql
    assert '"m"."student_id"' not in sql
    assert '"m"."course_id"' not in sql
    assert '"m"."score"' not in sql
    assert 'GROUP BY "student_id", "course_id";' in sql


def _sales_schema() -> dict:
    return {
        "tables": [
            {
                "name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER", "primary_key": True},
                    {"name": "customer_id", "type": "INTEGER", "primary_key": False},
                    {"name": "product_id", "type": "INTEGER", "primary_key": False},
                    {"name": "quantity", "type": "INTEGER", "primary_key": False},
                    {"name": "total_amount", "type": "REAL", "primary_key": False},
                    {"name": "order_date", "type": "DATE", "primary_key": False},
                ],
            },
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "type": "INTEGER", "primary_key": True},
                    {"name": "region", "type": "TEXT", "primary_key": False},
                    {"name": "segment", "type": "TEXT", "primary_key": False},
                ],
            },
            {
                "name": "products",
                "columns": [
                    {"name": "product_id", "type": "INTEGER", "primary_key": True},
                    {"name": "product_name", "type": "TEXT", "primary_key": False},
                    {"name": "category", "type": "TEXT", "primary_key": False},
                ],
            },
        ]
    }


def json_plan(sql_queries: list[str]) -> str:
    steps = [
        {
            "step_title": f"Step {index}",
            "purpose": "Exercise generated SQL normalization.",
            "sql_query": sql,
        }
        for index, sql in enumerate(sql_queries, start=1)
    ]
    return json.dumps({"steps": steps})


def _student_schema() -> dict:
    return {
        "tables": [
            {
                "name": "students",
                "columns": [
                    {"name": "student_id", "type": "INTEGER", "primary_key": True},
                    {"name": "student_name", "type": "TEXT", "primary_key": False},
                    {"name": "branch", "type": "TEXT", "primary_key": False},
                    {"name": "course", "type": "TEXT", "primary_key": False},
                    {"name": "marks", "type": "REAL", "primary_key": False},
                    {"name": "attendance", "type": "REAL", "primary_key": False},
                ],
            }
        ]
    }


def _student_join_schema() -> dict:
    return {
        "tables": [
            {
                "name": "students",
                "columns": [
                    {"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "name", "type": "TEXT", "primary_key": False},
                ],
            },
            {
                "name": "marks",
                "columns": [
                    {"name": "student_id", "type": "INTEGER", "primary_key": False},
                    {"name": "course_id", "type": "INTEGER", "primary_key": False},
                    {"name": "score", "type": "REAL", "primary_key": False},
                ],
            },
            {
                "name": "courses",
                "columns": [
                    {"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "course_name", "type": "TEXT", "primary_key": False},
                ],
            },
        ]
    }
