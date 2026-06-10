import httpx
import pytest

from sqlmind_agent.nim_client import (
    EXPLANATION_SYSTEM_PROMPT,
    MissingNvidiaApiKeyError,
    NIMClient,
    build_sql_prompt,
)


def test_generate_sql_uses_mocked_nim_response(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    class MockClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> "MockClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict, json: dict) -> httpx.Response:
            requests.append({"url": url, "headers": headers, "json": json})
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"choices": [{"message": {"content": "SELECT * FROM sales;"}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    client = NIMClient(
        api_key="test-key",
        base_url="https://example.test/v1/",
        model="test-model",
    )
    sql = client.generate_sql("show sales", {"tables": [{"name": "sales"}]})

    assert sql == "SELECT * FROM sales"
    assert requests[0]["url"] == "https://example.test/v1/chat/completions"
    assert requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert requests[0]["json"]["model"] == "test-model"
    assert "Return ONLY SQL" in requests[0]["json"]["messages"][0]["content"]


def test_generate_sql_prompt_includes_conversation_history(
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
                        {"message": {"content": "SELECT * FROM scores WHERE marks > 80"}}
                    ]
                },
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    client = NIMClient(api_key="test-key")
    client.generate_sql(
        "show only those above 80",
        {"tables": [{"name": "scores"}]},
        [
            {
                "question": "show marks by student",
                "sql": "SELECT student, marks FROM scores",
                "columns": ["student", "marks"],
                "result_preview": [{"student": "Asha", "marks": 91}],
                "explanation": "Asha scored 91.",
            }
        ],
    )

    user_prompt = requests[0]["messages"][1]["content"]
    assert "Conversation history:" in user_prompt
    assert "show marks by student" in user_prompt
    assert "show only those above 80" in user_prompt
    assert "follow-up" in user_prompt


def test_build_sql_prompt_limits_history_to_recent_items() -> None:
    history = [
        {"question": f"question {index}", "sql": "SELECT 1"}
        for index in range(7)
    ]

    prompt = build_sql_prompt("show top 5 from this", {"tables": []}, history)

    assert "question 0" not in prompt
    assert "question 1" not in prompt
    assert "question 2" in prompt
    assert "show top 5 from this" in prompt


def test_explain_results_uses_mocked_nim_response(monkeypatch: pytest.MonkeyPatch) -> None:
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
                json={"choices": [{"message": {"content": "Sales are highest in North."}}]},
            )

    monkeypatch.setattr("sqlmind_agent.nim_client.httpx.Client", MockClient)

    explanation = NIMClient(api_key="test-key").explain_results(
        "show sales",
        "SELECT * FROM sales",
        {"rows": [{"region": "North"}]},
    )

    assert explanation == "Sales are highest in North."


def test_explanation_prompt_requires_structured_markdown() -> None:
    assert "## Explanation" in EXPLANATION_SYSTEM_PROMPT
    assert "Return clean Markdown only" in EXPLANATION_SYSTEM_PROMPT
    assert "Do not include code fences" in EXPLANATION_SYSTEM_PROMPT
    assert "Do not include JSON" in EXPLANATION_SYSTEM_PROMPT
    assert "3 to 5 bullet points maximum" in EXPLANATION_SYSTEM_PROMPT


def test_missing_api_key_is_graceful() -> None:
    client = NIMClient(api_key=None)

    with pytest.raises(MissingNvidiaApiKeyError, match="NVIDIA_API_KEY is missing"):
        client.generate_sql("show sales", {"tables": []})
