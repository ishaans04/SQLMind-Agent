# Operations

## Environment Variables

SQLMind-Agent reads configuration from `.env`.

Common variables:

- `FASTAPI_BASE_URL`: Streamlit backend URL. Defaults to `http://127.0.0.1:8090`.
- `DATABASE_URL`: default demo database connection string.
- `NVIDIA_API_KEY`: NVIDIA NIM API key.
- `NVIDIA_BASE_URL`: NVIDIA NIM-compatible API base URL.
- `NVIDIA_MODEL`: Model used for SQL generation, Smart Analysis, and result explanations.
- `SQLMIND_MCP_SERVER_PATH`: local path to the SQLMind-MCP server entry point.

## Backend Startup

```powershell
python -m uvicorn sqlmind_agent.api:app --reload --port 8090
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/health
```

### Useful endpoints

- Health Check: `http://127.0.0.1:8090/health`
- API Docs: `http://127.0.0.1:8090/docs`

## React Frontend Startup

```powershell
cd frontend
npm install
npm run dev
```

### Frontend URL

`http://127.0.0.1:5173`

## Troubleshooting

### Backend Not Running

The frontend displays a connection error when it cannot reach the backend.

Verify:
`http://127.0.0.1:8090/health`

returns a healthy response.

If not, restart the FastAPI backend.

### Frontend Cannot Reach Backend

Verify that:
VITE_API_BASE_URL=`http://127.0.0.1:8090`

matches the backend port.


After modifying frontend environment variables:

```powershell
npm run dev
```

must be restarted.

### MCP Server Cannot Start

Confirm: 

- SQLMIND_MCP_SERVER_PATH points to the SQLMind-MCP server.py entry point.
- SQLMind-MCP dependencies are installed in the active Python environment.
- The MCP server can be launched independently before starting SQLMind-Agent.

### NVIDIA API Key Missing

Natural Language → SQL, Smart Analysis, Dashboard Generation, and AI explanations require:

NVIDIA_API_KEY=<your_api_key>

Schema inspection and direct database operations may still function without model calls.

### Query Blocked

SQLMind-Agent enforces read-only database access.

Allowed:

- SELECT
- Read-only CTEs (WITH ... SELECT)
- JOIN operations
- Aggregations
- GROUP BY
- ORDER BY
- LIMIT

Blocked:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- TRUNCATE
- Unsafe database commands

Queries that violate these rules are rejected before execution by the Safety Layer

## Operational Notes 

- SQLMind-Agent is designed for read-only analytics workflows.
- Database schema inspection is performed through SQLMind-MCP.
- SQL generation and explanations are handled through NVIDIA NIM.
- CSV and Excel exports are generated locally.
- Secrets, API keys, uploaded SQLite files, and local databases should not be committed to version control.