from typing import Any

import httpx

from sqlmind_agent.config import Settings, get_settings


class MissingNvidiaApiKeyError(ValueError):
    """Raised when the NIM client is used without credentials."""


class NIMClientError(RuntimeError):
    """Raised when NVIDIA NIM returns an unexpected or failed response."""


SQL_SYSTEM_PROMPT = """
You are SQLMind-Agent, a senior SQL analyst.
Generate one read-only SQL query for the user's question.
Use only the provided schema.
When the user asks a follow-up question, use the conversation history to resolve references
such as "those", "them", "this", "above 80", "sort them", "group by course",
"compare this with attendance", or "top 5 from this".
Return ONLY SQL. Do not include markdown, code fences, comments, or explanation.
Only read-only queries are allowed: SELECT, SHOW, DESCRIBE, EXPLAIN, or WITH.
""".strip()


EXPLANATION_SYSTEM_PROMPT = """
You are SQLMind-Agent, a concise executive analytics narrator.
Explain the SQL query results for the user's original question as clean Markdown.
Do not invent facts beyond the provided result rows.
Return clean Markdown only. Do not include code fences. Do not include JSON.
Do not include unnecessary blank lines. Do not write "Here is".
Use this exact format:

## Explanation
- What the query returned.
- Important pattern or observation.
- Any limitation if relevant.

Keep it concise with 3 to 5 bullet points maximum.
Make every bullet specific to the supplied SQL and result rows.
""".strip()


class NIMClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "meta/llama-3.1-8b-instruct",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings) -> "NIMClient":
        return cls(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_model,
        )

    def generate_sql(
        self,
        question: str,
        schema: dict[str, Any],
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> str:
        content = self._chat(
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_sql_prompt(question, schema, conversation_history or []),
                },
            ],
            temperature=0.0,
        )
        return _clean_sql(content)

    def explain_results(self, question: str, sql: str, results: dict[str, Any]) -> str:
        return self._chat(
            messages=[
                {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"SQL:\n{sql}\n\n"
                        f"Results:\n{results}"
                    ),
                },
            ],
            temperature=0.2,
        ).strip()

    def _chat(self, messages: list[dict[str, str]], temperature: float) -> str:
        if not self.api_key:
            raise MissingNvidiaApiKeyError(
                "NVIDIA_API_KEY is missing. Add it to .env before using /ask."
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise NIMClientError(f"NVIDIA NIM request failed: {error}") from error

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise NIMClientError("NVIDIA NIM returned an unexpected response shape.") from error


def generate_sql(
    question: str,
    schema: dict[str, Any],
    conversation_history: list[dict[str, Any]] | None = None,
) -> str:
    return NIMClient.from_settings(get_settings()).generate_sql(
        question,
        schema,
        conversation_history,
    )


def explain_results(question: str, sql: str, results: dict[str, Any]) -> str:
    return NIMClient.from_settings(get_settings()).explain_results(question, sql, results)


def build_sql_prompt(
    question: str,
    schema: dict[str, Any],
    conversation_history: list[dict[str, Any]],
) -> str:
    history = conversation_history[-5:]
    return (
        f"Schema:\n{schema}\n\n"
        f"Conversation history:\n{history if history else '[]'}\n\n"
        f"Current question:\n{question}\n\n"
        "If the current question is a follow-up, adapt the prior SQL using the provided "
        "history while staying within the current schema and read-only policy."
    )


def _clean_sql(content: str) -> str:
    sql = content.strip()
    if sql.startswith("```"):
        lines = [line for line in sql.splitlines() if not line.strip().startswith("```")]
        sql = "\n".join(lines).strip()
    return sql.rstrip(";")
