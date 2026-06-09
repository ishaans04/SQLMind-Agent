# Security Policy

## Supported Versions

SQLMind-Agent is currently pre-1.0. Security fixes are applied to the main development line unless release branches are introduced.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the project maintainers. If no private contact is listed for the repository, open a GitHub security advisory instead of filing a public issue.

Include:

- A clear description of the issue.
- Steps to reproduce, if safe to share.
- Impact and affected configuration.
- Any suggested mitigation.

## Security Model

SQLMind-Agent is designed for local, read-only analytics workflows.

- SQL safety validation blocks data modification and schema modification commands.
- Generated SQL is validated before execution.
- SQL execution is delegated to SQLMind-MCP.
- Passwords and database credentials should never be displayed, logged, or stored in query history.
- `.env`, uploaded databases, logs, and local caches must stay out of git.

## Out of Scope

Do not use SQLMind-Agent as a public internet service without adding production-grade authentication, authorization, network controls, audit logging, rate limiting, and secret management.
