from fastapi.testclient import TestClient

from sqlmind_agent.api import app, get_mcp_client, get_nim_client
from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.mcp_client import MCPClientError
from sqlmind_agent.nim_client import MissingNvidiaApiKeyError
from sqlmind_agent.schemas import ColumnInfo, QueryResults, SchemaResponse, TableInfo

SALES_SCHEMA = SchemaResponse(
    tables=[
        TableInfo(
            name="sales",
            columns=[
                ColumnInfo(name="id", type="INTEGER", nullable=True, primary_key=True),
                ColumnInfo(name="region", type="TEXT", nullable=False, primary_key=False),
                ColumnInfo(name="product", type="TEXT", nullable=False, primary_key=False),
                ColumnInfo(name="amount", type="REAL", nullable=False, primary_key=False),
            ],
        )
    ]
)

SALES_RESULTS = QueryResults(
    columns=["region", "total_sales"],
    rows=[
        {"region": "North", "total_sales": 25.0},
        {"region": "South", "total_sales": 7.5},
    ],
    row_count=2,
)


class MockMCPClient:
    def __init__(self, results: QueryResults = SALES_RESULTS):
        self.results = results
        self.last_sql: str | None = None

    def get_database_schema(self) -> SchemaResponse:
        return SALES_SCHEMA

    def run_select_query(self, sql: str) -> QueryResults:
        self.last_sql = sql
        return self.results


class FailingMCPClient:
    def get_database_schema(self) -> SchemaResponse:
        raise MCPClientError("SQLMind-MCP could not start or respond.")

    def run_select_query(self, sql: str) -> QueryResults:
        raise MCPClientError("SQLMind-MCP could not start or respond.")


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


def test_schema_uses_mcp_response() -> None:
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.get("/schema")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["tables"][0]["name"] == "sales"


def test_ask_sales_by_region() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        default_limit=50,
    )
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
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


def test_ask_blocks_unsafe_generated_sql() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: MockNIMClient("DROP TABLE sales")

    client = TestClient(app)
    response = client.post("/ask", json={"question": "delete sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 400


def test_ask_returns_graceful_error_when_nvidia_key_missing() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: MissingKeyNIMClient()

    client = TestClient(app)
    response = client.post("/ask", json={"question": "show sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "NVIDIA_API_KEY is missing" in response.json()["detail"]


def test_schema_returns_graceful_error_when_mcp_fails() -> None:
    app.dependency_overrides[get_mcp_client] = lambda: FailingMCPClient()

    client = TestClient(app)
    response = client.get("/schema")

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "SQLMind-MCP could not start" in response.json()["detail"]


def test_query_uses_mcp_response() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(default_limit=50)
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post("/query", json={"sql": "SELECT * FROM sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"] == ["region", "total_sales"]
    assert payload["rows"][0] == {"region": "North", "total_sales": 25.0}


def test_query_blocks_writes() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post("/query", json={"sql": "DROP TABLE sales"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
