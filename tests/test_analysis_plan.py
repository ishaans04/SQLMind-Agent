import httpx
import pytest

from sqlmind_agent.analysis_plan import (
    FINAL_REPORT_SYSTEM_PROMPT,
    AnalysisPlanner,
    _parse_json_object,
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

    schema = {
        "tables": [
            {
                "name": "students",
                "columns": [
                    {"name": "branch", "type": "TEXT"},
                    {"name": "marks", "type": "REAL"},
                ],
            }
        ]
    }
    steps = AnalysisPlanner(NIMClient(api_key="test-key")).generate_plan(
        "Analyze student performance",
        schema,
    )

    assert len(steps) == 3
    assert steps[0].sql_query == 'SELECT COUNT(*) AS total_records FROM "students"'
    assert "AVG" in steps[1].sql_query
    assert "GROUP BY" in steps[1].sql_query
