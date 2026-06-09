# Operations

## Environment Variables

SQLMind-Agent reads configuration from `.env`.

Common variables:

- `FASTAPI_BASE_URL`: Streamlit backend URL. Defaults to `http://127.0.0.1:8001`.
- `DATABASE_URL`: default demo database connection string.
- `NVIDIA_API_KEY`: NVIDIA NIM API key.
- `NVIDIA_BASE_URL`: NVIDIA NIM-compatible API base URL.
- `NVIDIA_MODEL`: model used for SQL generation and explanations.
- `SQLMIND_MCP_SERVER_PATH`: local path to the SQLMind-MCP server entry point.

## Backend Startup

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8001
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

## Streamlit Startup

```powershell
streamlit run streamlit_app.py
```

## Troubleshooting

### Backend Not Running

The Streamlit UI displays an error card when it cannot reach `FASTAPI_BASE_URL`. Start FastAPI and confirm `/health` returns `ok`.

### MCP Server Cannot Start

Confirm `SQLMIND_MCP_SERVER_PATH` points to the SQLMind-MCP `server.py` file and that the MCP project dependencies are installed in the same Python environment.

### NVIDIA API Key Missing

Natural-language SQL generation and result explanation require `NVIDIA_API_KEY`. Direct schema and query endpoints can still be used without model calls.

### Query Blocked

SQLMind-Agent is read-only. Data modification, schema modification, multiple statements, and unsafe database commands are rejected before execution.
