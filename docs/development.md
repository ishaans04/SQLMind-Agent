# Development

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Initialize the demo SQLite database:

```powershell
python scripts/init_demo_db.py
```

## Run the FastAPI Backend

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8090
```

### Backend URLs

- Health Check: `http://127.0.0.1:8090/health`
- API Docs: `http://127.0.0.1:8090/docs`

## Run the React Frontend

```powershell
cd frontend
npm install
npm run dev 
```

### Frontend URL

`http://127.0.0.1:5173`

## Full Local Development

Open two terminals

### Terminal 1 – Backend

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8090
```

### Terminal 2 – Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Available Services

Frontend: http://127.0.0.1:5173
Backend: http://127.0.0.1:8090
API Docs: http://127.0.0.1:8090/docs
Health Check: http://127.0.0.1:8090/health

## Run Tests

```powershell
python -m pytest
```

Current Status:

```text
85 tests passed

## Run the Optional Streamlit UI

```powershell
streamlit run streamlit_app.py
```

The Streamlit interface is maintained as an alternative local analytics dashboard and development interface. It provides a quick way to test backend functionality without the React frontend. It is not intended for production use or as the primary user interface.

## Lint

```powershell
ruff check .
```

## Development Notes

- Keep SQLMind-MCP changes isolated unless a task explicitly requires MCP modifications.
- Add tests for API behavior, SQL safety validation, dashboard generation, analytics workflows, and external client integrations.
- Mock NVIDIA NIM and database dependencies during testing.
- Do not call production databases or external AI services from tests.
- Keep secrets, API keys, uploaded SQLite files, generated local data, and database credentials out of version control.
- Maintain read-only SQL guarantees through the Safety Layer before query execution.