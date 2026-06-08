import httpx
import pytest

from sqlmind_agent.nim_client import MissingNvidiaApiKeyError, NIMClient


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


def test_missing_api_key_is_graceful() -> None:
    client = NIMClient(api_key=None)

    with pytest.raises(MissingNvidiaApiKeyError, match="NVIDIA_API_KEY is missing"):
        client.generate_sql("show sales", {"tables": []})
