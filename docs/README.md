# SQLMind-Agent Documentation

Welcome to the SQLMind-Agent documentation. These pages describe the project structure, operating model, and development workflow without duplicating the main setup instructions in the root README.

## Contents

- [Architecture](architecture.md): how the Streamlit UI, FastAPI API, SQLMind-MCP, and NVIDIA NIM pieces fit together.
- [Development](development.md): local development, test commands, and contribution checks.
- [Operations](operations.md): runtime configuration, environment variables, and troubleshooting notes.

## Project Principles

- SQLMind-Agent is read-only by design.
- Database execution is delegated to SQLMind-MCP.
- Natural-language SQL generation and explanations are delegated to NVIDIA NIM.
- The Streamlit UI is a client of the FastAPI backend.
- Security validation stays in front of every generated or submitted SQL query.
