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

## Run Tests

```powershell
python -m pytest
```

## Lint

```powershell
ruff check .
```

## Run the Backend

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8001
```

## Run the Streamlit UI

```powershell
streamlit run streamlit_app.py
```

## Development Notes

- Keep SQLMind-MCP changes separate unless a request explicitly requires MCP changes.
- Add tests for API behavior, safety validation, prompt construction, and mocked external clients.
- Do not call real NVIDIA APIs or real production databases from tests.
- Keep generated SQLite uploads and local secrets out of git.
