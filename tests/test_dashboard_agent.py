import httpx
import pytest

from sqlmind_agent.dashboard_agent import (
    DASHBOARD_REPORT_SYSTEM_PROMPT,
    DashboardAgent,
    fallback_dashboard_plan,
)
from sqlmind_agent.nim_client import NIMClient


def test_generate_dashboard_plan_from_mocked_nim_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                                  "dashboard_title": "Sales Executive Dashboard",
                                  "kpi_cards": [
                                    {
                                      "title": "Total Sales",
                                      "purpose": "Track total revenue.",
                                      "sql_query": "SELECT SUM(amount) AS total_sales FROM sales"
                                    }
                                  ],
                                  "chart_widgets": [
                                    {
                                      "title": "Sales by Region",
                                      "purpose": "Compare regional sales.",
                                      "sql_query": "SELECT region, amount FROM sales"
                                    }
                                  ],
                                  "table_widgets": [
                                    {
                                      "title": "Sales Detail",
                                      "purpose": "Preview sales rows.",
                                      "sql_query": "SELECT * FROM sales"
                                    }
                                  ],
                                  "insight_goals": ["Find the highest region."]
                                }
                                """
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    agent = DashboardAgent(NIMClient(api_key="test-key"))
    plan = agent.generate_plan("Create a sales dashboard", {"tables": []})

    assert plan.dashboard_title == "Sales Executive Dashboard"
    assert plan.kpi_cards[0].title == "Total Sales"
    assert plan.chart_widgets[0].sql_query.startswith("SELECT")
    assert "executive dashboard designer" in requests[0]["messages"][0]["content"]


def test_dashboard_report_prompt_requires_structured_markdown() -> None:
    assert "# Dashboard Insight Report" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "## Executive Summary" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "## KPI Interpretation" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "## Chart Insights" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "## Business / Academic Recommendations" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "## Risks & Follow-ups" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "Return clean Markdown only" in DASHBOARD_REPORT_SYSTEM_PROMPT
    assert "Do not include JSON" in DASHBOARD_REPORT_SYSTEM_PROMPT


def test_generate_dashboard_plan_falls_back_when_nim_returns_invalid_json(
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
                json={"choices": [{"message": {"content": "not json"}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    schema = {
        "tables": [
            {
                "name": "sales",
                "columns": [
                    {"name": "amount", "type": "REAL"},
                ],
            }
        ]
    }
    plan = DashboardAgent(NIMClient(api_key="test-key")).generate_plan(
        "Create a sales dashboard",
        schema,
    )

    assert plan.dashboard_title == "Create a sales dashboard"
    assert plan.kpi_cards[0].sql_query == 'SELECT COUNT(*) AS total_records FROM "sales"'
    assert plan.chart_widgets
    assert "CASE WHEN" in plan.chart_widgets[0].sql_query
    assert '"amount_range"' in plan.chart_widgets[0].sql_query
    assert '"amount_count"' in plan.chart_widgets[0].sql_query


def test_fallback_dashboard_plan_handles_empty_schema() -> None:
    plan = fallback_dashboard_plan("Create a dashboard", {"tables": []})

    assert plan.kpi_cards[0].sql_query == "SELECT 1 AS total_records"
    assert plan.table_widgets[0].sql_query == "SELECT 1 AS value"
