from fastapi.testclient import TestClient

from sqlmind_agent.api import (
    app,
    get_analysis_planner,
    get_connection_mcp_client,
    get_mcp_client,
    get_nim_client,
)
from sqlmind_agent.config import Settings, get_settings
from sqlmind_agent.mcp_client import MCPClientError
from sqlmind_agent.nim_client import MissingNvidiaApiKeyError
from sqlmind_agent.safety import READ_ONLY_MODE_MESSAGE
from sqlmind_agent.schemas import (
    AnalysisPlanStep,
    ColumnInfo,
    ConnectDatabaseRequest,
    ExecutedAnalysisStep,
    QueryResults,
    SchemaResponse,
    TableInfo,
)

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
        self.connected_config: ConnectDatabaseRequest | None = None

    def connect_database(self, config: ConnectDatabaseRequest) -> str:
        self.connected_config = config
        return f"Connected to {config.db_type} database."

    def get_database_schema(self) -> SchemaResponse:
        return SALES_SCHEMA

    def run_select_query(self, sql: str) -> QueryResults:
        self.last_sql = sql
        if "bad_table" in sql:
            raise MCPClientError("Requested table does not exist.")
        return self.results


class FailingMCPClient:
    def connect_database(self, config: ConnectDatabaseRequest) -> str:
        raise MCPClientError("SQLMind-MCP could not connect database.")

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

    def generate_sql(
        self,
        question: str,
        schema: dict,
        conversation_history: list[dict] | None = None,
    ) -> str:
        assert question
        assert schema["tables"][0]["name"] == "sales"
        return self.sql

    def explain_results(self, question: str, sql: str, results: dict) -> str:
        assert question
        assert sql
        assert results["row_count"] > 0
        return "North has the highest total sales in the result set."


class MissingKeyNIMClient:
    def generate_sql(
        self,
        question: str,
        schema: dict,
        conversation_history: list[dict] | None = None,
    ) -> str:
        raise MissingNvidiaApiKeyError(
            "NVIDIA_API_KEY is missing. Add it to .env before using /ask."
        )

    def explain_results(self, question: str, sql: str, results: dict) -> str:
        raise AssertionError("explain_results should not be called when SQL generation fails.")


class ExplodingNIMClient:
    def generate_sql(
        self,
        question: str,
        schema: dict,
        conversation_history: list[dict] | None = None,
    ) -> str:
        raise AssertionError("generate_sql should not be called for blocked prompts.")

    def explain_results(self, question: str, sql: str, results: dict) -> str:
        raise AssertionError("explain_results should not be called for blocked prompts.")


class MockAnalysisPlanner:
    def __init__(self, include_failed_step: bool = False):
        self.include_failed_step = include_failed_step

    def generate_plan(self, question: str, schema: dict) -> list[AnalysisPlanStep]:
        steps = [
            AnalysisPlanStep(
                step_title="Sales by region",
                purpose="Compare regional sales.",
                sql_query="SELECT region, SUM(amount) AS total_sales FROM sales GROUP BY region",
            ),
            AnalysisPlanStep(
                step_title="Sales by product",
                purpose="Compare product sales.",
                sql_query="SELECT product, SUM(amount) AS total_sales FROM sales GROUP BY product",
            ),
            AnalysisPlanStep(
                step_title="Total sales",
                purpose="Compute total sales.",
                sql_query="SELECT SUM(amount) AS total_sales FROM sales",
            ),
        ]
        if self.include_failed_step:
            steps[1] = AnalysisPlanStep(
                step_title="Broken step",
                purpose="Exercise graceful failure.",
                sql_query="SELECT * FROM bad_table",
            )
        return steps

    def final_report(self, question: str, executed_steps: list[ExecutedAnalysisStep]) -> str:
        failures = [step for step in executed_steps if not step.success]
        if failures:
            return "Analysis completed with one failed step."
        return "Regional and product sales were analyzed successfully."


def clear_overrides() -> None:
    app.dependency_overrides.clear()
    if hasattr(app.state, "database_config"):
        del app.state.database_config


def test_connect_database_uses_mcp_and_hides_password() -> None:
    app.dependency_overrides[get_connection_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post(
        "/connect-database",
        json={
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "school",
            "username": "admin",
            "password": "secret",
        },
    )

    clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "success": True,
        "db_type": "postgresql",
        "message": "Connected to postgresql database.",
    }
    assert "secret" not in response.text


def test_connect_database_requires_sqlite_file_path() -> None:
    app.dependency_overrides[get_connection_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post("/connect-database", json={"db_type": "sqlite"})

    clear_overrides()

    assert response.status_code == 400
    assert "sqlite_file_path is required" in response.json()["detail"]


def test_connect_database_returns_graceful_error_when_mcp_fails() -> None:
    app.dependency_overrides[get_connection_mcp_client] = lambda: FailingMCPClient()

    client = TestClient(app)
    response = client.post(
        "/connect-database",
        json={"db_type": "sqlite", "sqlite_file_path": "data/demo.db"},
    )

    clear_overrides()

    assert response.status_code == 503
    assert "could not connect" in response.json()["detail"]


def test_schema_uses_mcp_response() -> None:
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.get("/schema")

    clear_overrides()

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

    clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "show total sales by region"
    assert payload["sql"].endswith("LIMIT 50")
    assert payload["results"]["columns"] == ["region", "total_sales"]
    assert payload["results"]["rows"][0] == {"region": "North", "total_sales": 25.0}
    assert payload["explanation"] == "North has the highest total sales in the result set."


def test_ask_passes_conversation_history_to_nim() -> None:
    captured_history: list[dict] | None = None

    class CapturingNIMClient(MockNIMClient):
        def generate_sql(
            self,
            question: str,
            schema: dict,
            conversation_history: list[dict] | None = None,
        ) -> str:
            nonlocal captured_history
            captured_history = conversation_history
            return "SELECT region, SUM(amount) AS total_sales FROM sales GROUP BY region"

    app.dependency_overrides[get_settings] = lambda: Settings(default_limit=50)
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: CapturingNIMClient()

    client = TestClient(app)
    response = client.post(
        "/ask",
        json={
            "question": "show only those above 80",
            "conversation_history": [
                {
                    "question": "show marks by student",
                    "sql": "SELECT student, marks FROM scores",
                    "columns": ["student", "marks"],
                    "result_preview": [{"student": "Asha", "marks": 91}],
                    "explanation": "Asha scored 91.",
                }
            ],
        },
    )

    clear_overrides()

    assert response.status_code == 200
    assert captured_history is not None
    assert captured_history[0]["question"] == "show marks by student"
    assert captured_history[0]["result_preview"] == [{"student": "Asha", "marks": 91}]


def test_ask_blocks_unsafe_generated_sql() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: MockNIMClient("DROP TABLE sales")

    client = TestClient(app)
    response = client.post("/ask", json={"question": "delete sales"})

    clear_overrides()

    assert response.status_code == 400


def test_ask_blocks_mutation_prompt_before_llm() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: ExplodingNIMClient()

    client = TestClient(app)
    response = client.post("/ask", json={"question": "drop the sales table"})

    clear_overrides()

    assert response.status_code == 400
    assert response.json()["detail"] == READ_ONLY_MODE_MESSAGE


def test_ask_returns_graceful_error_when_nvidia_key_missing() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_nim_client] = lambda: MissingKeyNIMClient()

    client = TestClient(app)
    response = client.post("/ask", json={"question": "show sales"})

    clear_overrides()

    assert response.status_code == 503
    assert "NVIDIA_API_KEY is missing" in response.json()["detail"]


def test_analyze_executes_plan_and_returns_report() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(default_limit=10)
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_analysis_planner] = lambda: MockAnalysisPlanner()

    client = TestClient(app)
    response = client.post("/analyze", json={"question": "Analyze sales performance", "limit": 10})

    clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "Analyze sales performance"
    assert len(payload["analysis_plan"]) == 3
    assert len(payload["executed_steps"]) == 3
    assert all(step["success"] for step in payload["executed_steps"])
    assert (
        payload["final_insight_report"]
        == "Regional and product sales were analyzed successfully."
    )
    assert payload["chart_suggestions"]


def test_analyze_continues_when_one_step_fails() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(default_limit=10)
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()
    app.dependency_overrides[get_analysis_planner] = lambda: MockAnalysisPlanner(
        include_failed_step=True
    )

    client = TestClient(app)
    response = client.post("/analyze", json={"question": "Analyze sales performance", "limit": 10})

    clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed_steps"][1]["success"] is False
    assert "bad_table" in payload["executed_steps"][1]["sql_query"]
    assert payload["executed_steps"][2]["success"] is True
    assert payload["final_insight_report"] == "Analysis completed with one failed step."


def test_schema_returns_graceful_error_when_mcp_fails() -> None:
    app.dependency_overrides[get_mcp_client] = lambda: FailingMCPClient()

    client = TestClient(app)
    response = client.get("/schema")

    clear_overrides()

    assert response.status_code == 503
    assert "SQLMind-MCP could not start" in response.json()["detail"]


def test_query_uses_mcp_response() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(default_limit=50)
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post("/query", json={"sql": "SELECT * FROM sales"})

    clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"] == ["region", "total_sales"]
    assert payload["rows"][0] == {"region": "North", "total_sales": 25.0}


def test_query_blocks_writes() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mcp_client] = lambda: MockMCPClient()

    client = TestClient(app)
    response = client.post("/query", json={"sql": "DROP TABLE sales"})

    clear_overrides()

    assert response.status_code == 400
