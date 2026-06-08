# SQLMind-Agent

SQLMind-Agent is a local, read-only SQL assistant. It exposes a small FastAPI service that can inspect a SQLite database, use NVIDIA NIM to translate natural-language questions into safe `SELECT` queries, execute them, and return the generated SQL, rows, and an AI explanation.

The repository was scaffolded from an empty `PRD.md`, so V1 makes conservative assumptions:

- SQLite first, with a demo database for local development.
- Read-only SQL execution only.
- NVIDIA NIM integration for SQL generation and result explanation.
- Existing safety validation still blocks non-`SELECT` SQL before execution.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/init_demo_db.py
Copy-Item .env.example .env
# Edit .env and set NVIDIA_API_KEY.
uvicorn sqlmind_agent.api:app --reload
```

Then open:

- API health: `http://127.0.0.1:8000/health`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Example Request

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"show total sales by region","limit":10}'
```

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
NVIDIA_API_KEY=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
```

If `NVIDIA_API_KEY` is missing, `/ask` returns a graceful `503` error. `/schema` and `/query` continue to work without an NVIDIA key.

## Project Layout

```text
sqlmind_agent/
  api.py              FastAPI routes
  config.py           Runtime settings
  database.py         SQLite schema inspection and execution
  nim_client.py       NVIDIA NIM chat-completions client
  planner.py          Natural-language to SQL starter planner
  safety.py           Read-only SQL validation
  schemas.py          API models
scripts/
  init_demo_db.py     Creates data/demo.db
tests/
  test_*.py           Unit and API tests
```

## V1 Scope

V1 is intentionally small but usable:

- `GET /health` reports service status.
- `GET /schema` returns discovered tables and columns.
- `POST /ask` generates SQL through NVIDIA NIM, validates it, executes it, and explains the results.
- `POST /query` executes a caller-provided read-only SQL query.

## Next Milestones

- Add support for PostgreSQL and SQL Server through SQLAlchemy connection URLs.
- Add per-table permissions, row limits, audit logging, and saved query history.
- Add a web UI for schema browsing and conversational query refinement.
