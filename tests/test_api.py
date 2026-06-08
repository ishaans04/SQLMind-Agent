import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from sqlmind_agent.api import app, get_nim_client
from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.nim_client import MissingNvidiaApiKeyError


def create_test_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                region TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL
            );

            INSERT INTO sales (region, product, amount) VALUES
                ('North', 'Analytics Pro', 10.0),
                ('North', 'Data Studio', 15.0),
                ('South', 'Analytics Pro', 7.5);
            """
        )


class MockNIMClient:
    def __init__(
        self,
        sql: str = "SELECT region, SUM(amount) AS total_sales FROM sales GROUP BY region",
    ):
        self.sql = sql

    def generate_sql(self, question: str, schema: dict) -> str:
        assert question
        assert schema["tables"][0]["name"] == "sales"
        return self.sql

    def explain_results(self, question: str, sql: str, results: dict) -> str:
        assert question
        assert sql
        assert results["row_count"] > 0
        return "North has the highest total sales in the result set."


class MissingKeyNIMClient:
    def generate_sql(self, question: str, schema: dict) -> str:
        raise MissingNvidiaApiKeyError(
            "NVIDIA_API_KEY is missing. Add it to .env before using /ask."
        )

    def explain_results(self, question: str, sql: str, results: dict) -> str:
        raise AssertionError("explain_results should not be called when SQL generation fails.")


def test_ask_sales_by_region(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    create_test_db(database_path)
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_path=database_path,
        default_limit=50,
    )
    app.dependency_overrides[get_nim_client] = lambda: MockNIMClient()

    client = TestClient(app)
    response = client.post("/ask", json={"question": "show total sales by region"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "show total sales by region"
    assert payload["sql"].endswith("LIMIT 50")
    assert payload["results"]["columns"] == ["region", "total_sales"]
    assert payload["results"]["rows"][0] == {"region": "North", "total_sales": 25.0}
    assert payload["explanation"] == "North has the highest total sales in the result set."


def test_ask_blocks_unsafe_generated_sql(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    create_test_db(database_path)
    app.dependency_overrides[get_settings] = lambda: Settings(database_path=database_path)
    app.dependency_overrides[get_nim_client] = lambda: MockNIMClient("DROP TABLE sales")

    client = TestClient(app)
    response = client.post("/ask", json={"question": "delete sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 400


def test_ask_returns_graceful_error_when_nvidia_key_missing(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    create_test_db(database_path)
    app.dependency_overrides[get_settings] = lambda: Settings(database_path=database_path)
    app.dependency_overrides[get_nim_client] = lambda: MissingKeyNIMClient()

    client = TestClient(app)
    response = client.post("/ask", json={"question": "show sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "NVIDIA_API_KEY is missing" in response.json()["detail"]


def test_query_blocks_writes(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    create_test_db(database_path)
    app.dependency_overrides[get_settings] = lambda: Settings(database_path=database_path)

    client = TestClient(app)
    response = client.post("/query", json={"sql": "DROP TABLE sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
