from __future__ import annotations

import html
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

DEFAULT_FASTAPI_BASE_URL = "http://127.0.0.1:8001"
REQUEST_TIMEOUT_SECONDS = 12
UPLOAD_DIR = Path("data/uploads")
READ_ONLY_MODE_MESSAGE = "Command not allowed. SQLMind Agent is running in read-only mode."
CHART_OPTIONS = ["Auto", "Bar Chart", "Line Chart", "Pie Chart", "No Chart"]


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


def ask_backend(
    question: str,
    limit: int,
    conversation_history: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            api_url("/ask"),
            json={
                "question": question,
                "limit": limit,
                "conversation_history": conversation_history,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = _error_detail(error.response)
        return None, detail or str(error)
    except requests.RequestException as error:
        return None, str(error)
    return response.json(), None


def analyze_backend(question: str, limit: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            api_url("/analyze"),
            json={"question": question, "limit": limit},
            timeout=REQUEST_TIMEOUT_SECONDS * 3,
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = _error_detail(error.response)
        return None, detail or str(error)
    except requests.RequestException as error:
        return None, str(error)
    return response.json(), None


def connect_database_backend(config: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    safe_config = {key: value for key, value in config.items() if value not in (None, "")}
    try:
        response = requests.post(
            api_url("/connect-database"),
            json=safe_config,
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
    if "connected_database" not in st.session_state:
        st.session_state.connected_database = "Default demo SQLite database"
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "last_analysis" not in st.session_state:
        st.session_state.last_analysis = None
    if "conversation_memory" not in st.session_state:
        st.session_state.conversation_memory = []


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

        .error-card {
            background: rgba(255, 82, 82, .13);
            border: 1px solid rgba(255, 120, 120, .38);
            border-radius: 8px;
            color: #ffd6d6;
            padding: 1rem;
            font-weight: 750;
            margin-bottom: 1rem;
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

        .section-heading {
            font-size: 1rem;
            font-weight: 800;
            margin: 1.1rem 0 .65rem;
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
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] div {
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


def error_card(message: str) -> None:
    st.markdown(
        f'<div class="error-card">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def result_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    rows = payload.get("results", {}).get("rows", [])
    return pd.DataFrame(rows)


def infer_auto_chart(df: pd.DataFrame) -> str:
    numeric_columns = numeric_column_names(df)
    if df.empty or not numeric_columns:
        return "No Chart"

    date_columns = date_column_names(df)
    if date_columns:
        return "Line Chart"

    category_columns = category_column_names(df)
    if not category_columns:
        return "No Chart"

    if df[category_columns[0]].nunique(dropna=True) <= 6:
        return "Pie Chart"
    return "Bar Chart"


def numeric_column_names(df: pd.DataFrame) -> list[str]:
    return list(df.select_dtypes(include="number").columns)


def category_column_names(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in df.columns
        if column not in numeric_column_names(df) and column not in date_column_names(df)
    ]


def date_column_names(df: pd.DataFrame) -> list[str]:
    date_columns: list[str] = []
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            date_columns.append(column)
            continue
        lowered = str(column).lower()
        if "date" not in lowered and "time" not in lowered:
            continue
        parsed = pd.to_datetime(df[column], errors="coerce")
        if parsed.notna().any():
            date_columns.append(column)
    return date_columns


def build_chart(df: pd.DataFrame, chart_choice: str) -> tuple[Any | None, str | None]:
    chart_type = infer_auto_chart(df) if chart_choice == "Auto" else chart_choice
    if chart_type == "No Chart":
        if chart_choice == "No Chart":
            message = "No chart selected."
        else:
            message = "No chartable columns found."
        return None, message

    numeric_columns = numeric_column_names(df)
    if not numeric_columns:
        return None, "No numeric columns exist, so a chart cannot be generated."

    value_column = numeric_columns[0]
    try:
        if chart_type == "Line Chart":
            date_columns = date_column_names(df)
            if not date_columns:
                return None, "Line chart needs a date or time column."
            x_column = date_columns[0]
            chart_df = df.copy()
            chart_df[x_column] = pd.to_datetime(chart_df[x_column], errors="coerce")
            chart_df = chart_df.dropna(subset=[x_column])
            return px.line(chart_df, x=x_column, y=value_column, markers=True), None

        category_columns = category_column_names(df)
        if not category_columns:
            return None, "Chart needs a category column."
        category_column = category_columns[0]

        if chart_type == "Pie Chart":
            grouped = df.groupby(category_column, dropna=False)[value_column].sum().reset_index()
            if len(grouped) > 10:
                return None, "Pie chart works best with fewer categories."
            return px.pie(grouped, names=category_column, values=value_column), None

        grouped = df.groupby(category_column, dropna=False)[value_column].sum().reset_index()
        return px.bar(grouped, x=category_column, y=value_column), None
    except Exception as error:
        return None, f"Chart cannot be generated: {error}"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    return buffer.getvalue()


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
                label = f"{column.get('name')} - {column.get('type')}"
                if column.get("primary_key"):
                    label += " - PK"
                st.caption(label)


def render_connection_panel(connected: bool) -> None:
    st.sidebar.markdown("### Database Connection")
    st.sidebar.caption(f"Connected: {st.session_state.connected_database}")

    db_type_label = st.sidebar.selectbox("Database type", ["SQLite", "PostgreSQL", "MySQL"])
    db_type = db_type_label.lower()
    config: dict[str, Any] = {"db_type": db_type}

    if db_type == "sqlite":
        sqlite_file_path = st.sidebar.text_input("SQLite .db file path", value="data/demo.db")
        uploaded_file = st.sidebar.file_uploader(
            "Upload SQLite .db",
            type=["db", "sqlite", "sqlite3"],
        )
        if uploaded_file is not None:
            sqlite_file_path = save_uploaded_database(uploaded_file)
            st.sidebar.caption(f"Uploaded file staged at {sqlite_file_path}")
        config["sqlite_file_path"] = sqlite_file_path
    else:
        default_port = 5432 if db_type == "postgresql" else 3306
        config["host"] = st.sidebar.text_input("Host", value="localhost")
        config["port"] = int(
            st.sidebar.number_input("Port", min_value=1, max_value=65_535, value=default_port)
        )
        config["database_name"] = st.sidebar.text_input("Database name")
        config["username"] = st.sidebar.text_input("Username")
        config["password"] = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Connect Database", disabled=not connected, use_container_width=True):
        payload, error = connect_database_backend(config)
        if error:
            st.sidebar.error(error)
            return
        if payload:
            st.session_state.connected_database = connection_label(config)
            st.session_state.query_history = []
            st.sidebar.success(payload.get("message", "Database connected."))
            st.rerun()


def save_uploaded_database(uploaded_file: Any) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(uploaded_file.name).name.replace(" ", "_")
    file_path = UPLOAD_DIR / f"{uuid4().hex}_{original_name}"
    file_path.write_bytes(uploaded_file.getbuffer())
    return str(file_path)


def connection_label(config: dict[str, Any]) -> str:
    db_type = config.get("db_type")
    if db_type == "sqlite":
        return f"SQLite - {Path(str(config.get('sqlite_file_path', ''))).name}"
    return f"{str(db_type).title()} - {config.get('database_name')}@{config.get('host')}"


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


def render_conversation_memory() -> None:
    st.sidebar.markdown("### Conversation Memory")
    if st.sidebar.button("Clear Memory", use_container_width=True):
        st.session_state.conversation_memory = []
        st.session_state.query_history = []
        st.session_state.last_result = None
        st.rerun()

    memory = st.session_state.conversation_memory
    if not memory:
        st.sidebar.caption("Follow-up context will appear here.")
        return

    for item in reversed(memory[-5:]):
        question = html.escape(item.get("question", ""))
        columns = ", ".join(item.get("columns", [])[:4])
        st.sidebar.markdown(
            f"""
            <div class="history-item">
                <strong>{question}</strong><br/>
                <span class="muted">Columns: {html.escape(columns)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def compact_result_preview(df: pd.DataFrame, max_rows: int = 5) -> list[dict[str, Any]]:
    return df.head(max_rows).to_dict(orient="records")


def append_conversation_memory(payload: dict[str, Any]) -> None:
    df = result_dataframe(payload)
    memory_item = {
        "question": payload.get("question", ""),
        "sql": payload.get("sql", ""),
        "columns": list(df.columns),
        "result_preview": compact_result_preview(df),
        "explanation": payload.get("explanation", ""),
    }
    st.session_state.conversation_memory.append(memory_item)
    st.session_state.conversation_memory = st.session_state.conversation_memory[-10:]


def render_result(payload: dict[str, Any]) -> None:
    sql = html.escape(payload.get("sql", ""))
    explanation = html.escape(payload.get("explanation", ""))
    results = payload.get("results", {})
    df = result_dataframe(payload)
    row_count = results.get("row_count", len(df))

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

    st.markdown('<div class="section-heading">Result Table</div>', unsafe_allow_html=True)
    st.markdown(f"<p class='muted'>{row_count} rows returned</p>", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-heading">Chart</div>', unsafe_allow_html=True)
    chart_choice = st.selectbox("Chart selector", CHART_OPTIONS)
    figure, chart_error = build_chart(df, chart_choice)
    if figure is not None:
        figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=35, b=20),
        )
        st.plotly_chart(figure, use_container_width=True)
    elif chart_error:
        st.info(chart_error)

    st.markdown('<div class="section-heading">Export</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("No rows available to export.")
        return

    export_left, export_right = st.columns(2)
    with export_left:
        st.download_button(
            "Download CSV",
            data=dataframe_to_csv_bytes(df),
            file_name="sqlmind_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with export_right:
        st.download_button(
            "Download Excel",
            data=dataframe_to_excel_bytes(df),
            file_name="sqlmind_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_analysis(payload: dict[str, Any]) -> None:
    st.markdown('<div class="section-heading">Analysis Plan</div>', unsafe_allow_html=True)
    for index, step in enumerate(payload.get("analysis_plan", []), start=1):
        card(
            f"Step {index}: {step.get('step_title', '')}",
            f"<p>{html.escape(step.get('purpose', ''))}</p>",
        )

    st.markdown('<div class="section-heading">Executed Steps</div>', unsafe_allow_html=True)
    for index, step in enumerate(payload.get("executed_steps", []), start=1):
        step_title = html.escape(step.get("step_title", ""))
        purpose = html.escape(step.get("purpose", ""))
        sql_query = html.escape(step.get("sql_query", ""))
        st.markdown(
            f"""
            <div class="card sql-card">
                <div class="card-title">Step {index}: {step_title}</div>
                <p class="muted">{purpose}</p>
                <pre>{sql_query}</pre>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not step.get("success"):
            error_card(step.get("error", "Step failed."))
            continue

        result_payload = {"results": step.get("results", {})}
        df = result_dataframe(result_payload)
        st.dataframe(df, use_container_width=True, hide_index=True)
        figure, chart_error = build_chart(df, "Auto")
        if figure is not None:
            figure.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=35, b=20),
            )
            st.plotly_chart(figure, use_container_width=True)
        elif chart_error:
            st.info(chart_error)

    st.markdown('<div class="section-heading">Result Summaries</div>', unsafe_allow_html=True)
    for summary in payload.get("result_summaries", []):
        st.markdown(f"- {summary}")

    st.markdown('<div class="section-heading">Chart Suggestions</div>', unsafe_allow_html=True)
    for suggestion in payload.get("chart_suggestions", []):
        st.markdown(f"- {suggestion}")

    card("Final Insight Report", f"<p>{html.escape(payload.get('final_insight_report', ''))}</p>")


def main() -> None:
    load_dotenv()
    print(f"SQLMind-Agent Streamlit Python executable: {sys.executable}")
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
        render_connection_panel(connected)
        render_schema(schema_payload, schema_error)
        render_conversation_memory()
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

    mode = st.radio(
        "Mode",
        ["Ask Mode", "Smart Analysis Mode"],
        horizontal=True,
    )

    question = st.text_area(
        "Natural language input",
        placeholder=(
            "Example: Show average marks by course for second-year students"
            if mode == "Ask Mode"
            else "Example: Analyze student performance"
        ),
        height=110,
    )

    controls_left, controls_right = st.columns([1, 4])
    with controls_left:
        limit = st.number_input("Limit", min_value=1, max_value=500, value=50, step=10)
    with controls_right:
        st.write("")
        action_label = "Ask" if mode == "Ask Mode" else "Run Smart Analysis"
        ask_clicked = st.button(action_label, use_container_width=False, disabled=not connected)

    if not connected:
        st.error("FastAPI backend is not running. Start it on port 8001, then refresh this page.")

    if ask_clicked and mode == "Ask Mode":
        if not question.strip():
            st.warning("Enter a question before asking SQLMind.")
            return

        with st.spinner("Generating SQL and querying the database..."):
            payload, error = ask_backend(
                question.strip(),
                int(limit),
                st.session_state.conversation_memory,
            )

        if error:
            if error == READ_ONLY_MODE_MESSAGE:
                error_card(READ_ONLY_MODE_MESSAGE)
            else:
                st.error(error)
            return

        if payload:
            st.session_state.last_result = payload
            st.session_state.last_analysis = None
            append_conversation_memory(payload)
            st.session_state.query_history.append(
                {
                    "question": payload.get("question", question.strip()),
                    "sql": payload.get("sql", ""),
                    "row_count": payload.get("results", {}).get("row_count", 0),
                }
            )

    if ask_clicked and mode == "Smart Analysis Mode":
        if not question.strip():
            st.warning("Enter an analysis question before running Smart Analysis.")
            return

        with st.spinner("Planning and running smart analysis..."):
            payload, error = analyze_backend(question.strip(), int(limit))

        if error:
            if error == READ_ONLY_MODE_MESSAGE:
                error_card(READ_ONLY_MODE_MESSAGE)
            else:
                st.error(error)
            return

        if payload:
            st.session_state.last_analysis = payload
            st.session_state.last_result = None

    if st.session_state.last_result:
        render_result(st.session_state.last_result)
    if st.session_state.last_analysis:
        render_analysis(st.session_state.last_analysis)


if __name__ == "__main__":
    main()
