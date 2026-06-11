# Architecture

User
 │
 ▼
React Frontend
 │
 ▼
FastAPI Backend
 │
 ├── Safety Layer
 ├── Planner Agent
 ├── Dashboard Agent
 ├── NVIDIA NIM
 └── MCP Client
         │
         ▼
     SQLMind-MCP
         │
         ▼
SQLite / MySQL / PostgreSQL


SQLMind-Agent is organized as a local analytics assistant with clear boundaries between UI, API, model calls, and database execution.

## Components

### React Frontend

The React frontend (Vite + TypeScript + Tailwind CSS) provides the primary user interface for SQLMind-Agent. It supports:

- Natural Language → SQL
- Smart Analysis workflows
- Executive Dashboard generation
- Interactive visualizations
- Query history
- Database schema exploration
- CSV and Excel exports

The frontend communicates with the FastAPI backend through REST APIs.

### Streamlit UI (Optional)

`streamlit_app.py` serves as an alternative interface for local analytics workflows and development testing. It exposes the same backend functionality through a Streamlit-based dashboard.

### FastAPI Backend

`sqlmind_agent/api.py` exposes the API surface:

- `GET /health`
- `GET /schema`
- `POST /query`
- `POST /ask`
- `POST /analyze`
- `POST /connect-database`

The backend validates SQL safety before execution and coordinates calls between NVIDIA NIM and SQLMind-MCP.

### NVIDIA NIM Client

`sqlmind_agent/nim_client.py` handles natural-language SQL generation and result explanations. Requests that violate read-only intent should be rejected before reaching the model.

### SQLMind-MCP Client

`sqlmind_agent/mcp_client.py` treats SQLMind-MCP as an external local MCP tool server. SQLMind-Agent calls MCP tools for database connection, schema lookup, and read-only query execution.

### Safety Layer

`sqlmind_agent/safety.py` rejects unsafe prompts and SQL before execution. Only read-only query forms are allowed, including `SELECT` and read-only CTE queries that ultimately resolve to `SELECT`.

### Dashboard Agent

The dashboard generation layer converts analytical requests into KPI cards, charts, and executive summaries. It automatically selects relevant metrics, executes safe SQL queries, and produces visualization-ready outputs for the frontend.

## Data Flow

1. A user interacts with the React frontend or optional Streamlit interface.
2. FastAPI validates request intent.
3. FastAPI retrieves database schema through SQLMind-MCP.
4. NVIDIA NIM generates SQL or analysis plans.
5. Safety Layer validates generated SQL.
6. SQLMind-MCP executes approved read-only queries.
7. NVIDIA NIM generates explanations, insights, and summaries.
8. FastAPI returns structured results.
9. React renders tables, charts, dashboards, and exports.
