# SQLMind-Agent

SQLMind-Agent is a local, read-only SQL assistant. It exposes a small FastAPI service that calls SQLMind-MCP for database connection, schema, and query execution, uses NVIDIA NIM to translate natural-language questions into safe `SELECT` queries, and returns generated SQL, rows, and an AI explanation.

The repository was scaffolded from an empty `PRD.md`, so V1 makes conservative assumptions:

- SQLMind-MCP is treated as an external local tool server over stdio.
- SQLite, PostgreSQL, and MySQL connections are initiated through SQLMind-MCP.
- Read-only SQL execution only.
- NVIDIA NIM integration for SQL generation and result explanation.
- Existing safety validation still blocks non-`SELECT` SQL before execution.

## Key Features

- Natural Language → SQL
- Multi-Database Support (SQLite, MySQL, PostgreSQL)
- MCP Integration
- NVIDIA NIM Integration
- Smart Analytics Agent
- Conversational Memory
- Interactive Charts
- CSV & Excel Export
- Enterprise Streamlit Dashboard
- Read-Only Security Layer

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/init_demo_db.py
Copy-Item .env.example .env
# Edit .env and set NVIDIA_API_KEY and SQLMIND_MCP_SERVER_PATH if needed.
uvicorn sqlmind_agent.api:app --reload --port 8001
```

Then open:

- API health: `http://127.0.0.1:8001/health`
- OpenAPI docs: `http://127.0.0.1:8001/docs`

## Tech Stack

### Frontend
- Streamlit

### Backend
- FastAPI

### AI Layer
- NVIDIA NIM
- Llama 3.1 8B

### Database Layer
- SQLite
- MySQL
- PostgreSQL

### Protocol
- Model Context Protocol (MCP)

### Analytics
- Plotly
- Pandas

### Testing
- Pytest
- Ruff

### CI/CD
- GitHub Actions

## Example Request

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8001/ask `
  -ContentType "application/json" `
  -Body '{"question":"show total sales by region","limit":10}'
```

## Streamlit UI

Run the API and UI in two terminals:

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8001
```

```powershell
streamlit run streamlit_app.py
```

The Streamlit app reads `FASTAPI_BASE_URL` from `.env`, defaulting to `http://127.0.0.1:8001`. It shows an enterprise-style analytics dashboard with backend, MCP, database, and NIM status pills; database schema; query history; conversation memory; generated SQL; AI explanation; result rows; visual analytics; and exports.

The sidebar includes a database connection panel:

- SQLite: enter a `.db` path or upload a `.db`/`.sqlite` file.
- PostgreSQL: host, port `5432`, database name, username, and password.
- MySQL: host, port `3306`, database name, username, and password.

Passwords are sent only to the backend connection endpoint and are never displayed in responses or query history. Uploaded SQLite files are staged under `data/uploads/`, which is ignored by git.

For screenshots or demos, start both terminals above, open the Streamlit URL printed in the terminal, connect the demo SQLite database, and run an example question such as `Show attendance by student`.

### Conversational Memory

SQLMind stores recent query context in Streamlit session state so follow-up questions can reuse previous results. Stored memory includes:

- Previous user questions
- Generated SQL
- Result columns
- A short result preview
- AI explanations

This lets users ask follow-ups such as `show only those above 80`, `sort them by marks`, `now group by course`, `compare this with attendance`, or `show top 5 from this`. Use `Clear Memory` in the sidebar to remove the current session memory. Passwords and database credentials are never stored in memory.

### Smart Analysis Mode

Use the mode selector to switch from `Ask Mode` to `Smart Analysis Mode`. Smart Analysis accepts broad analytical requests such as `Analyze student performance`, asks NVIDIA NIM for a 3 to 5 step analysis plan, validates every generated query with the existing read-only safety layer, executes each safe query through SQLMind-MCP, and returns:

- Analysis plan
- Executed SQL for each step
- Result tables
- Automatic charts when possible
- Result summaries
- Chart suggestions
- Final insight report

If one step fails, SQLMind reports that step and continues running the remaining analysis steps.

### Visual Analytics

After each successful question, SQLMind displays the result table and a chart section powered by Plotly. Use the chart selector to choose:

- Auto
- Bar Chart
- Line Chart
- Pie Chart
- No Chart

Auto mode chooses a chart from the result shape:

- Category plus numeric values: bar chart
- Date/time plus numeric values: line chart
- Few categories plus numeric values: pie chart

If no numeric columns exist or the chart cannot be generated, the UI shows a clear message and keeps the table visible.

### CSV Export

Use `Download CSV` in the export section to save the current query results as `sqlmind_results.csv`.

### Excel Export

Use `Download Excel` in the export section to save the current query results as `sqlmind_results.xlsx`. Excel export uses `openpyxl`.

`POST /ask` returns:

```json
{
  "question": "show total sales by region",
  "sql": "SELECT ... LIMIT 10",
  "results": {
    "columns": ["region", "total_sales"],
    "rows": [],
    "row_count": 0
  },
  "explanation": "..."
}
```

## Configuration

Values are read from `.env`.

```text
SQLMIND_DATABASE_PATH=data/demo.db
SQLMIND_DEFAULT_LIMIT=50
SQLMIND_MCP_SERVER_PATH=../SQLMind-MCP/server.py
FASTAPI_BASE_URL=http://127.0.0.1:8001
# The app uses the SQLMind-MCP default demo SQLite database until /connect-database is called.
NVIDIA_API_KEY=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
```

If `NVIDIA_API_KEY` is missing, `/ask` returns a graceful `503` error. `/schema` and `/query` continue to work without an NVIDIA key.

If SQLMind-MCP cannot start or respond, the API returns a graceful `503` error. SQLMind-Agent does not modify SQLMind-MCP; it starts the configured `server.py` with the official MCP Python SDK stdio client and calls:

- `connect_database`
- `get_database_schema`
- `run_select_query`

## Project Layout

```text
sqlmind_agent/
  api.py              FastAPI routes
  config.py           Runtime settings
  database.py         SQLite schema inspection and execution
  mcp_client.py       SQLMind-MCP stdio client
  nim_client.py       NVIDIA NIM chat-completions client
  planner.py          Natural-language to SQL starter planner
  safety.py           Read-only SQL validation
  schemas.py          API models
scripts/
  init_demo_db.py     Creates data/demo.db
streamlit_app.py      Streamlit dashboard UI
tests/
  test_*.py           Unit and API tests
```

## V1 Scope

V1 is intentionally small but usable:

- `GET /health` reports service status.
- `POST /connect-database` connects SQLite, PostgreSQL, or MySQL through SQLMind-MCP.
- `GET /schema` returns discovered tables and columns from SQLMind-MCP.
- `POST /ask` fetches schema from MCP, generates SQL through NVIDIA NIM, validates it, executes through MCP, and explains the results.
- `POST /analyze` generates a multi-step analysis plan through NVIDIA NIM, validates and executes each SELECT query through SQLMind-MCP, and returns a final insight report.
- `POST /query` validates caller-provided SQL and executes it through SQLMind-MCP.

## Next Milestones

- Add support for PostgreSQL and SQL Server through SQLAlchemy connection URLs.
- Add per-table permissions, row limits, audit logging, and saved query history.
- Add a web UI for schema browsing and conversational query refinement.
