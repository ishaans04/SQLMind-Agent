# Contributing

Thanks for helping improve SQLMind-Agent.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/init_demo_db.py
Copy-Item .env.example .env
```

## Before Opening a Pull Request

Run:

```powershell
python -m pytest
ruff check .
```

## Contribution Guidelines

- Keep application logic changes focused and covered by tests.
- Do not commit `.env`, uploaded databases, logs, virtual environments, or generated caches.
- Use mocked external services in tests. Do not call real NVIDIA NIM APIs in CI.
- Keep SQLMind-Agent and SQLMind-MCP boundaries clear. SQLMind-Agent should treat SQLMind-MCP as an external tool server unless a task explicitly requires MCP changes.
- Preserve the read-only security model for generated and submitted SQL.

## Reporting Issues

When reporting a bug, include:

- The command or UI action that failed.
- The expected result.
- The actual result or error message.
- Your Python version and operating system.
- Whether SQLMind-MCP and FastAPI were running.
