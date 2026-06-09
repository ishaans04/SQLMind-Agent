# Architecture

SQLMind-Agent is organized as a local analytics assistant with clear boundaries between UI, API, model calls, and database execution.

## Components

### Streamlit UI

`streamlit_app.py` provides the user-facing dashboard. It calls the FastAPI backend for health checks, schema retrieval, natural-language questions, and smart analysis requests.

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

## Data Flow

1. A user asks a question in Streamlit or through the API.
2. FastAPI checks read-only prompt intent.
3. FastAPI fetches schema through SQLMind-MCP.
4. NVIDIA NIM generates SQL.
5. FastAPI validates generated SQL.
6. SQLMind-MCP executes the safe query.
7. NVIDIA NIM explains the results.
8. FastAPI returns SQL, rows, and explanation to the caller.
