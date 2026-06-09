from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

DEFAULT_FASTAPI_BASE_URL = "http://127.0.0.1:8001"
REQUEST_TIMEOUT_SECONDS = 12


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_url(path: str) -> str:
    base_url = os.getenv("FASTAPI_BASE_URL", DEFAULT_FASTAPI_BASE_URL).rstrip("/")
    return f"{base_url}{path}"


def get_backend_status() -> tuple[bool, str]:
    try:
        response = requests.get(api_url("/health"), timeout=4)
        response.raise_for_status()
    except requests.RequestException as error:
        return False, f"Backend offline: {error}"
    return True, "Backend connected"


def get_schema() -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.get(api_url("/schema"), timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        return None, str(error)
    return response.json(), None


def ask_backend(question: str, limit: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            api_url("/ask"),
            json={"question": question, "limit": limit},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = _error_detail(error.response)
        return None, detail or str(error)
    except requests.RequestException as error:
        return None, str(error)
    return response.json(), None


def _error_detail(response: requests.Response | None) -> str | None:
    if response is None:
        return None
    try:
        payload = response.json()
    except ValueError:
        return response.text
    detail = payload.get("detail")
    return detail if isinstance(detail, str) else str(detail)


def ensure_session_state() -> None:
    if "query_history" not in st.session_state:
        st.session_state.query_history = []


def render_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #080b12;
            --panel: #111722;
            --panel-soft: #151d2b;
            --line: rgba(255,255,255,.09);
            --text: #ecfdf5;
            --muted: #93a4b8;
            --green: #41e28a;
            --purple: #9d7cff;
        }

        .stApp {
            background:
                linear-gradient(135deg, rgba(65,226,138,.08), transparent 28%),
                linear-gradient(225deg, rgba(157,124,255,.10), transparent 30%),
                var(--bg);
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: #0b111a;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] * {
            color: var(--text);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1240px;
        }

        h1, h2, h3 {
            letter-spacing: 0;
        }

        .app-title {
            font-size: 2.1rem;
            font-weight: 760;
            margin: 0 0 .25rem;
        }

        .subtitle {
            color: var(--muted);
            font-size: .98rem;
            margin-bottom: 1.2rem;
        }

        .card {
            background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 18px 50px rgba(0,0,0,.25);
            margin-bottom: 1rem;
        }

        .card-title {
            color: var(--text);
            font-size: .82rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: .65rem;
        }

        .muted {
            color: var(--muted);
        }

        .status-ok, .status-bad {
            border-radius: 999px;
            padding: .35rem .7rem;
            font-size: .82rem;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--line);
        }

        .status-ok {
            color: var(--green);
            background: rgba(65,226,138,.10);
        }

        .status-bad {
            color: #ff9c9c;
            background: rgba(255,82,82,.11);
        }

        .sql-card pre {
            white-space: pre-wrap;
            color: #d6ffe8;
            background: #0a1018;
            border: 1px solid rgba(65,226,138,.22);
            border-radius: 12px;
            padding: .9rem;
            margin: 0;
        }

        .accent {
            color: var(--purple);
            font-weight: 700;
        }

        .history-item {
            border-bottom: 1px solid var(--line);
            padding: .65rem 0;
        }

        .history-item:last-child {
            border-bottom: 0;
        }

        div.stButton > button {
            background: linear-gradient(135deg, var(--green), var(--purple));
            color: #07100c;
            border: 0;
            border-radius: 12px;
            font-weight: 800;
            padding: .75rem 1rem;
        }

        div.stButton > button:hover {
            color: #07100c;
            filter: brightness(1.06);
        }

        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input {
            background: var(--panel);
            color: var(--text);
            border: 1px solid var(--line);
            border-radius: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">{html.escape(title)}</div>
            <div>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_schema(schema: dict[str, Any] | None, error: str | None) -> None:
    st.sidebar.markdown("### Database Schema")
    if error:
        st.sidebar.error(error)
        return
    if not schema:
        st.sidebar.caption("No schema loaded.")
        return

    for table in schema.get("tables", []):
        with st.sidebar.expander(table.get("name", "table"), expanded=False):
            for column in table.get("columns", []):
                label = f"{column.get('name')} · {column.get('type')}"
                if column.get("primary_key"):
                    label += " · PK"
                st.caption(label)


def render_history() -> None:
    st.sidebar.markdown("### Query History")
    history = st.session_state.query_history
    if not history:
        st.sidebar.caption("Questions you ask will appear here.")
        return

    for item in reversed(history[-8:]):
        question = html.escape(item["question"])
        rows = item["row_count"]
        st.sidebar.markdown(
            f"""
            <div class="history-item">
                <strong>{question}</strong><br/>
                <span class="muted">{rows} rows returned</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_result(payload: dict[str, Any]) -> None:
    sql = html.escape(payload.get("sql", ""))
    explanation = html.escape(payload.get("explanation", ""))
    results = payload.get("results", {})
    rows = results.get("rows", [])
    row_count = results.get("row_count", len(rows))

    st.markdown(
        f"""
        <div class="card sql-card">
            <div class="card-title">Generated SQL</div>
            <pre>{sql}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )
    card("AI Explanation", f"<p>{explanation}</p>")
    st.markdown(f"<p class='muted'>{row_count} rows returned</p>", unsafe_allow_html=True)
    st.dataframe(rows, use_container_width=True, hide_index=True)


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="SQLMind Agent", layout="wide", initial_sidebar_state="expanded")
    ensure_session_state()
    render_css()

    connected, status_text = get_backend_status()
    schema_payload, schema_error = get_schema() if connected else (None, status_text)

    with st.sidebar:
        st.markdown("## SQLMind")
        status_class = "status-ok" if connected else "status-bad"
        st.markdown(
            f'<span class="{status_class}">{html.escape(status_text)}</span>',
            unsafe_allow_html=True,
        )
        st.caption(os.getenv("FASTAPI_BASE_URL", DEFAULT_FASTAPI_BASE_URL))
        render_schema(schema_payload, schema_error)
        render_history()

    st.markdown('<div class="app-title">SQLMind Agent</div>', unsafe_allow_html=True)
    st.markdown(
        (
            '<div class="subtitle">'
            "Ask questions in plain English. Review SQL, explanation, and results."
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    question = st.text_area(
        "Natural language input",
        placeholder="Example: Show average marks by course for second-year students",
        height=110,
    )

    controls_left, controls_right = st.columns([1, 4])
    with controls_left:
        limit = st.number_input("Limit", min_value=1, max_value=500, value=50, step=10)
    with controls_right:
        st.write("")
        ask_clicked = st.button("Ask", use_container_width=False, disabled=not connected)

    if not connected:
        st.error("FastAPI backend is not running. Start it on port 8001, then refresh this page.")

    if ask_clicked:
        if not question.strip():
            st.warning("Enter a question before asking SQLMind.")
            return

        with st.spinner("Generating SQL and querying the database..."):
            payload, error = ask_backend(question.strip(), int(limit))

        if error:
            st.error(error)
            return

        if payload:
            st.session_state.query_history.append(
                {
                    "question": payload.get("question", question.strip()),
                    "sql": payload.get("sql", ""),
                    "row_count": payload.get("results", {}).get("row_count", 0),
                }
            )
            render_result(payload)


if __name__ == "__main__":
    main()
