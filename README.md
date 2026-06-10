# SQLMind-Agent

SQLMind-Agent is a local, read-only SQL assistant. It exposes a small FastAPI service that calls SQLMind-MCP for database connection, schema, and query execution, uses NVIDIA NIM to translate natural-language questions into safe `SELECT` queries, and returns generated SQL, rows, and an AI explanation.

The repository was scaffolded from an empty `PRD.md`, so V1 makes conservative assumptions:

- SQLMind-MCP is treated as an external local tool server over stdio.
- SQLite, PostgreSQL, and MySQL connections are initiated through SQLMind-MCP.
- Read-only SQL execution only.
- NVIDIA NIM integration for SQL generation and result explanation.
- Existing safety validation still blocks non-`SELECT` SQL before execution.

## Dependencies

SQLMind-Agent uses SQLMind-MCP as its database execution layer.

SQLMind-MCP is responsible for:

- Database connections
- Schema discovery
- Safe query execution
- Multi-database support

### SQLMind-MCP Repository

https://github.com/ishaans04/SQLMind-MCP

### Clone Both Repositories

To run SQLMind-Agent locally, clone both repositories into the same parent directory.

```bash
git clone https://github.com/ishaans04/SQLMind-MCP.git
git clone https://github.com/ishaans04/SQLMind-Agent.git
```

Expected folder structure:
```text
Desktop/
├── SQLMind-MCP/
└── SQLMind-Agent/
```

### Why is SQLMind-MCP separate?

SQLMind-Agent focuses on AI-powered analytics, natural-language SQL generation, visualization, and reporting.

SQLMind-MCP is a reusable database execution layer that can be integrated with other AI agents and applications.

## Key Features

### AI & Analytics

- Natural Language → SQL Generation
- Smart Analytics Agent
- AI-Generated Executive Insights
- Conversational Memory
- NVIDIA NIM Integration

### Data Connectivity

- Multi-Database Support (SQLite, MySQL, PostgreSQL)
- SQLMind-MCP Integration
- Schema Discovery & Exploration

### Dashboards & Visualization

- Dashboard Generator
- Executive KPI Dashboards
- Interactive Charts & Visual Analytics
- Branch-wise & Performance Analytics

### Export & Reporting

- CSV Export
- Excel Export
- Executive Dashboard Reports

### Platform & Security

- React + Vite Enterprise Frontend
- FastAPI Backend Services
- Read-Only Security Layer
- Automated SQL Safety Validation
- GitHub Actions CI/CD

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

- React
- Vite
- TypeScript
- Tailwind CSS
- Radix UI
- Recharts
- Streamlit (legacy/fallback UI)

### Backend

- FastAPI
- Python

### AI Layer

- NVIDIA NIM
- Llama 3.1 8B Instruct

### Database Layer

- SQLite
- MySQL
- PostgreSQL

### Protocol

- Model Context Protocol (MCP)

### Analytics & Visualization

- Plotly
- Pandas

### Testing & Quality

- Pytest
- Ruff

### CI

- GitHub Actions

## Example Request

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8001/ask `
  -ContentType "application/json" `
  -Body '{"question":"show total sales by region","limit":10}'
```

## React Frontend

SQLMind-Agent also includes a production-grade React frontend under `frontend/`. The Streamlit app remains available as a fallback.

Run the FastAPI backend first:

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8001
```

Then start the React app:

```powershell
cd frontend
npm install
npm run dev
```

The React frontend reads `VITE_API_BASE_URL` from `frontend/.env`, defaulting from `frontend/.env.example` to:

```text
VITE_API_BASE_URL=http://127.0.0.1:8001
```

The React UI provides:

- Sidebar navigation for Ask, Smart Analysis, Dashboard, Connections, and History
- Multi-database connection panel for SQLite, PostgreSQL, and MySQL
- Backend, MCP, database, and NVIDIA NIM status bar
- Generated SQL, result tables, charts, explanations, and CSV/Excel exports
- Smart Analysis plan cards, executed SQL sections, charts, and final insight report
- Dashboard Mode with KPI cards, chart grid, tables, generated SQL, and AI insights

## Streamlit UI (Legacy / Fallback)

The original Streamlit interface remains available for development, testing, and demos.

Run:

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8001
streamlit run streamlit_app.py
```
> The React frontend is the recommended production interface. Streamlit is a legacy fallback that can be useful for quick demos, testing, and development.

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

### Dashboard Mode

Use the mode selector to switch to `Dashboard Mode`. Dashboard Mode accepts broad executive dashboard requests, asks NVIDIA NIM for a dashboard plan, validates every widget query with the existing read-only safety layer, executes safe queries through SQLMind-MCP, and renders:

- Dashboard title
- KPI cards
- Chart widgets
- Table widgets
- Generated SQL expandable sections
- Final AI insight report
- CSV and Excel exports for widget result tables

Example dashboard prompts:

- `Generate a student performance dashboard`
- `Create a sales dashboard`
- `Build an attendance analytics dashboard`
- `Create a fees summary dashboard`

If one widget query fails, SQLMind shows the failed widget and continues rendering the remaining dashboard widgets. If a chart cannot be generated from a widget result, the UI falls back to a table.

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

`POST /dashboard` accepts:

```json
{
  "prompt": "Create a sales dashboard",
  "limit": 10
}
```

It returns the dashboard title, KPI widgets, chart widgets, table widgets, generated SQL, and a final insight report.

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


## Example Workflow

User:
Show average marks by branch

↓

NVIDIA NIM generates SQL

↓

Safety Layer validates query

↓

SQLMind-MCP executes query

↓

Results returned

↓

Charts generated

↓

AI explanation generated


## Current Capabilities

V1 is intentionally small but usable:

- `GET /health` reports service status.
- `POST /connect-database` connects SQLite, PostgreSQL, or MySQL through SQLMind-MCP.
- `GET /schema` returns discovered tables and columns from SQLMind-MCP.
- `POST /ask` fetches schema from MCP, generates SQL through NVIDIA NIM, validates it, executes through MCP, and explains the results.
- `POST /analyze` generates a multi-step analysis plan through NVIDIA NIM, validates and executes each SELECT query through SQLMind-MCP, and returns a final insight report.
- `POST /query` validates caller-provided SQL and executes it through SQLMind-MCP.

## Next Milestones

- User Authentication
- Saved Dashboards
- PDF Report Export
- Dashboard Templates
- Scheduled Reports
- Cloud Deployment
- Team Workspaces
- Role-Based Access Control