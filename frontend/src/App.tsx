import * as Tabs from "@radix-ui/react-tabs";
import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Database,
  History,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  PlugZap,
  Server,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  API_BASE_URL,
  API_BASE_URL_SOURCE,
  analyze,
  ask,
  connectDatabase,
  dashboard,
  getHealth,
  getSchema
} from "./lib/api";
import type {
  AnalysisResponse,
  AskResponse,
  ConnectionConfig,
  DashboardResponse,
  DbType,
  HistoryItem,
  Mode,
  SchemaResponse
} from "./types";
import { ChartPanel } from "./components/ChartPanel";
import { DataTable } from "./components/DataTable";
import { ExportButtons } from "./components/Exports";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, inputClass } from "./components/ui";
import { cn } from "./lib/utils";

const navItems: Array<{ id: Mode; label: string; icon: typeof MessageSquareText }> = [
  { id: "ask", label: "Ask", icon: MessageSquareText },
  { id: "analysis", label: "Smart Analysis", icon: BrainCircuit },
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "connections", label: "Connections", icon: PlugZap },
  { id: "history", label: "History", icon: History }
];

export default function App() {
  const [mode, setMode] = useState<Mode>("ask");
  const [backendStatus, setBackendStatus] = useState({ ok: false, message: "Checking" });
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [databaseLabel, setDatabaseLabel] = useState("Default demo SQLite database");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [dashboardResult, setDashboardResult] = useState<DashboardResponse | null>(null);

  async function refreshStatus() {
    const health = await getHealth();
    setBackendStatus(health);
    if (!health.ok) return;
    const schemaResponse = await getSchema();
    setSchema(schemaResponse.data);
    setSchemaError(schemaResponse.error);
  }

  useEffect(() => {
    void refreshStatus();
  }, []);

  const mcpReady = backendStatus.ok && !schemaError;
  const nimConfigured = true;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 border-r border-border bg-white/95 px-4 py-5 lg:block">
          <div className="mb-8 flex items-center gap-4 rounded-2xl px-3 py-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm">
              <Database className="h-6 w-6" />
            </div>
            <div className="min-w-0 text-left">
              <div className="truncate text-[30px] font-bold leading-none tracking-tight text-slate-950">
                SQLMind
              </div>
              <div className="mt-1 text-sm font-medium leading-5 text-slate-600">
                AI Database Intelligence
              </div>
              <div className="mt-1 text-[12.5px] leading-5 text-slate-400 [overflow-wrap:anywhere]">
                SQLite • MySQL • PostgreSQL
              </div>
            </div>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setMode(item.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition",
                    mode === item.id
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
          <div className="mt-8 rounded-xl border border-border bg-slate-50 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Read-only mode
            </div>
            <p className="text-xs leading-5 text-slate-500">
              SQL generation and execution stay behind the existing backend safety layer.
            </p>
          </div>
        </aside>

        <main className="flex-1 overflow-hidden">
          <header className="border-b border-border bg-white/80 px-5 py-4 backdrop-blur">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-700">
                  <Sparkles className="h-4 w-4" />
                  Production dashboard
                </div>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
                  SQLMind Agent
                </h1>
                <p className="text-sm text-slate-500">
                  Ask questions, run analysis plans, and generate executive dashboards from connected databases.
                </p>
              </div>
              <StatusBar
                backend={backendStatus.ok}
                mcp={mcpReady}
                database={Boolean(databaseLabel)}
                nim={nimConfigured}
              />
            </div>
          </header>

          <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="min-w-0 space-y-5">
              {!backendStatus.ok && (
                <ErrorBanner message={`Backend unavailable: ${backendStatus.message}`} />
              )}
              {mode === "ask" && (
                <AskMode
                  disabled={!backendStatus.ok}
                  result={askResult}
                  onResult={(result, prompt) => {
                    setAskResult(result);
                    setAnalysisResult(null);
                    setDashboardResult(null);
                    addHistory(setHistory, "Ask", prompt, result.results.row_count);
                  }}
                />
              )}
              {mode === "analysis" && (
                <SmartAnalysisMode
                  disabled={!backendStatus.ok}
                  result={analysisResult}
                  onStart={() => setAnalysisResult(null)}
                  onResult={(result, prompt) => {
                    setAnalysisResult(result);
                    setAskResult(null);
                    setDashboardResult(null);
                    addHistory(setHistory, "Smart Analysis", prompt);
                  }}
                />
              )}
              {mode === "dashboard" && (
                <DashboardMode
                  disabled={!backendStatus.ok}
                  result={dashboardResult}
                  onResult={(result, prompt) => {
                    setDashboardResult(result);
                    setAskResult(null);
                    setAnalysisResult(null);
                    addHistory(setHistory, "Dashboard", prompt);
                  }}
                />
              )}
              {mode === "connections" && (
                <ConnectionPanel
                  disabled={!backendStatus.ok}
                  onConnected={(label) => {
                    setDatabaseLabel(label);
                    void refreshStatus();
                  }}
                />
              )}
              {mode === "history" && <HistoryPanel items={history} />}
            </section>

            <aside className="space-y-5">
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold">Connection</h2>
                    <p className="mt-1 text-sm text-slate-500">{databaseLabel}</p>
                  </div>
                  <Badge tone="success">Connected</Badge>
                </div>
                <Button
                  className="mt-4 w-full"
                  variant="secondary"
                  onClick={() => setMode("connections")}
                >
                  Manage connection
                </Button>
              </Card>
              <SchemaCard schema={schema} error={schemaError} />
              <Card>
                <h2 className="text-sm font-semibold">API Base URL</h2>
                <p className="mt-2 break-all rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                  {API_BASE_URL}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Resolved from: <span className="font-semibold">{API_BASE_URL_SOURCE}</span>
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Debug: import.meta.env.VITE_API_BASE_URL ={" "}
                  {import.meta.env.VITE_API_BASE_URL || "(missing)"}
                </p>
              </Card>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}

function StatusBar({
  backend,
  mcp,
  database,
  nim
}: {
  backend: boolean;
  mcp: boolean;
  database: boolean;
  nim: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <StatusPill label="Backend" ok={backend} icon={Server} />
      <StatusPill label="MCP" ok={mcp} icon={Activity} />
      <StatusPill label="Database" ok={database} icon={Database} />
      <StatusPill label="NIM" ok={nim} icon={CheckCircle2} />
    </div>
  );
}

function StatusPill({
  label,
  ok,
  icon: Icon
}: {
  label: string;
  ok: boolean;
  icon: typeof Server;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold",
        ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

function AskMode({
  disabled,
  result,
  onResult
}: {
  disabled: boolean;
  result: AskResponse | null;
  onResult: (result: AskResponse, prompt: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);
    const response = await ask(question, limit);
    setLoading(false);
    if (response.error || !response.data) {
      setError(response.error ?? "Ask request failed.");
      return;
    }
    onResult(response.data, question);
  }

  return (
    <div className="space-y-5">
      <PromptCard
        title="Ask a question"
        description="Translate natural language into safe SQL, results, charts, and an explanation."
        placeholder="Show average marks by course"
        value={question}
        onChange={setQuestion}
        limit={limit}
        setLimit={setLimit}
        disabled={disabled || loading || !question.trim()}
        loading={loading}
        action="Ask SQLMind"
        onSubmit={submit}
      />
      {error && <ErrorBanner message={error} />}
      {!result ? (
        <EmptyState
          title="No question run yet"
          message="Ask a database question to see SQL, tables, charts, explanations, and exports."
        />
      ) : (
        <ResultWorkspace result={result} />
      )}
    </div>
  );
}

function ResultWorkspace({ result }: { result: AskResponse }) {
  return (
    <div className="space-y-5">
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Generated SQL</h2>
          <Badge>Read-only</Badge>
        </div>
        <pre className="overflow-auto rounded-lg bg-slate-950 p-4 text-sm leading-6 text-slate-100">
          {result.sql}
        </pre>
      </Card>
      <Tabs.Root defaultValue="results">
        <Tabs.List className="mb-4 flex flex-wrap gap-2 rounded-xl border border-border bg-white p-1 shadow-sm">
          {["results", "chart", "explanation", "export"].map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="rounded-lg px-4 py-2 text-sm font-semibold capitalize text-slate-500 data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700"
            >
              {tab}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="results">
          <DataTable results={result.results} />
        </Tabs.Content>
        <Tabs.Content value="chart">
          <ChartPanel results={result.results} />
        </Tabs.Content>
        <Tabs.Content value="explanation">
          <ReportCard
            eyebrow="Query explanation"
            title="AI Explanation"
            markdown={result.explanation}
          />
        </Tabs.Content>
        <Tabs.Content value="export">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Exports</h2>
            <ExportButtons results={result.results} filename="sqlmind_results" />
          </Card>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function SmartAnalysisMode({
  disabled,
  result,
  onStart,
  onResult
}: {
  disabled: boolean;
  result: AnalysisResponse | null;
  onStart: () => void;
  onResult: (result: AnalysisResponse, prompt: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);
    onStart();
    const response = await analyze(prompt, limit);
    setLoading(false);
    if (response.error || !response.data) {
      setError(response.error ?? "Smart Analysis failed.");
      return;
    }
    onResult(response.data, prompt);
  }

  return (
    <div className="space-y-5">
      <PromptCard
        title="Smart Analysis"
        description="Run a multi-step analytical workflow with safe SQL and a final report."
        placeholder="Analyze student performance"
        value={prompt}
        onChange={setPrompt}
        limit={limit}
        setLimit={setLimit}
        disabled={disabled || loading || !prompt.trim()}
        loading={loading}
        action="Run analysis"
        onSubmit={submit}
      />
      {error && <ErrorBanner message={error} />}
      {loading ? (
        <EmptyState
          title="Running multi-query analysis"
          message="SQLMind is planning and executing every safe analysis step for this prompt."
        />
      ) : !result ? (
        <EmptyState
          title="No analysis yet"
          message="Submit a broad request to generate an analysis plan."
        />
      ) : (
        <div className="space-y-5">
          <Card>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">
                  Multi-query analysis output
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {result.executed_steps.length} planned SQL steps were executed or reported
                  individually for this prompt.
                </p>
              </div>
              <Badge tone="success">
                {result.executed_steps.filter((step) => step.success).length} successful
              </Badge>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-3">
            {result.analysis_plan.map((step, index) => (
              <Card key={step.step_title}>
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-blue-50 text-sm font-bold text-blue-700">
                  {index + 1}
                </div>
                <h3 className="font-semibold">{step.step_title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">{step.purpose}</p>
              </Card>
            ))}
          </div>
          {result.executed_steps.map((step, index) => (
            <Card key={`${step.step_title}-${index}`} className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                    Query {index + 1} of {result.executed_steps.length}
                  </div>
                  <h3 className="mt-1 font-semibold">{step.step_title}</h3>
                </div>
                <Badge tone={step.success ? "success" : "danger"}>
                  {step.success ? "Success" : "Failed"}
                </Badge>
              </div>
              <details>
                <summary className="cursor-pointer text-sm font-semibold text-blue-700">
                  Executed SQL
                </summary>
                <pre className="mt-3 overflow-auto rounded-lg bg-slate-950 p-4 text-sm text-slate-100">
                  {step.sql_query}
                </pre>
              </details>
              {step.success ? (
                <Tabs.Root defaultValue="results">
                  <Tabs.List className="mb-4 flex flex-wrap gap-2 rounded-xl border border-border bg-white p-1 shadow-sm">
                    {["results", "chart", "export"].map((tab) => (
                      <Tabs.Trigger
                        key={tab}
                        value={tab}
                        className="rounded-lg px-4 py-2 text-sm font-semibold capitalize text-slate-500 data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700"
                      >
                        {tab}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>
                  <Tabs.Content value="results">
                    <DataTable results={step.results} />
                  </Tabs.Content>
                  <Tabs.Content value="chart">
                    <ChartPanel results={step.results} />
                  </Tabs.Content>
                  <Tabs.Content value="export">
                    <ExportButtons
                      results={step.results}
                      filename={`smart_analysis_${index + 1}_${slug(step.step_title)}`}
                    />
                  </Tabs.Content>
                </Tabs.Root>
              ) : (
                <ErrorBanner message={step.error ?? "Step failed."} />
              )}
            </Card>
          ))}
          <ReportCard
            eyebrow="Smart analysis report"
            title="Final Insight Report"
            markdown={result.final_insight_report}
          />
        </div>
      )}
    </div>
  );
}

function DashboardMode({
  disabled,
  result,
  onResult
}: {
  disabled: boolean;
  result: DashboardResponse | null;
  onResult: (result: DashboardResponse, prompt: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);
    const response = await dashboard(prompt, limit);
    setLoading(false);
    if (response.error || !response.data) {
      setError(response.error ?? "Dashboard generation failed.");
      return;
    }
    onResult(response.data, prompt);
  }

  return (
    <div className="space-y-5">
      <PromptCard
        title="Dashboard Generator"
        description="Create KPI cards, charts, tables, SQL, and executive insights from a dashboard request."
        placeholder="Generate a student performance dashboard"
        value={prompt}
        onChange={setPrompt}
        limit={limit}
        setLimit={setLimit}
        disabled={disabled || loading || !prompt.trim()}
        loading={loading}
        action="Generate dashboard"
        onSubmit={submit}
      />
      {error && <ErrorBanner message={error} />}
      {!result ? (
        <EmptyState
          title="No dashboard generated"
          message="Try prompts like Create a sales dashboard or Build an attendance analytics dashboard."
        />
      ) : (
        <div className="space-y-5">
          <Card>
            <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">{result.dashboard_title}</h2>
                <p className="mt-1 text-sm text-slate-500">{result.prompt}</p>
              </div>
              <Badge tone="success">Generated</Badge>
            </div>
          </Card>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {result.kpis.map((kpi) => (
              <Card key={kpi.title} className="min-w-0 overflow-hidden">
                <div className="truncate text-sm font-medium text-slate-500">{kpi.title}</div>
                <div
                  className="mt-3 max-w-full overflow-hidden text-ellipsis break-words text-3xl font-semibold leading-tight tracking-tight text-slate-950 [overflow-wrap:anywhere] sm:text-4xl"
                  title={kpi.success ? String(kpi.value ?? "-") : "-"}
                >
                  {kpi.success ? formatKpiValue(kpi.value, kpi.title) : "-"}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {kpi.success ? kpi.purpose : kpi.error}
                </p>
              </Card>
            ))}
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            {result.charts.map((widget) => (
              <Card key={widget.title} className="space-y-4">
                <h3 className="font-semibold">{widget.title}</h3>
                {widget.success ? (
                  <ChartPanel results={widget.results} />
                ) : (
                  <ErrorBanner message={widget.error ?? "Widget failed."} />
                )}
              </Card>
            ))}
          </div>
          {result.tables.map((widget) => (
            <Card key={widget.title} className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{widget.title}</h3>
                {widget.success && (
                  <ExportButtons
                    results={widget.results}
                    filename={slug(widget.title)}
                  />
                )}
              </div>
              {widget.success ? (
                <DataTable results={widget.results} />
              ) : (
                <ErrorBanner message={widget.error ?? "Widget failed."} />
              )}
            </Card>
          ))}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Generated SQL</h2>
            <div className="space-y-3">
              {result.generated_sql.map((item) => (
                <details key={`${item.widget_type}-${item.title}`} className="rounded-lg border border-border p-3">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                    {item.widget_type.toUpperCase()} · {item.title}
                  </summary>
                  <pre className="mt-3 overflow-auto rounded-lg bg-slate-950 p-4 text-sm text-slate-100">
                    {item.sql_query}
                  </pre>
                </details>
              ))}
            </div>
          </Card>
          <ReportCard
            eyebrow="Executive analytics report"
            title="AI Insights"
            markdown={result.final_insight_report}
          />
        </div>
      )}
    </div>
  );
}

function PromptCard({
  title,
  description,
  placeholder,
  value,
  onChange,
  limit,
  setLimit,
  disabled,
  loading,
  action,
  onSubmit
}: {
  title: string;
  description: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  limit: number;
  setLimit: (value: number) => void;
  disabled: boolean;
  loading: boolean;
  action: string;
  onSubmit: () => void;
}) {
  return (
    <Card>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <Field label="Row limit">
          <input
            className={cn(inputClass, "w-28")}
            type="number"
            min={1}
            max={500}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </Field>
      </div>
      <textarea
        className={cn(inputClass, "min-h-32 resize-y")}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="mt-4 flex justify-end">
        <Button disabled={disabled} onClick={onSubmit}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {action}
        </Button>
      </div>
    </Card>
  );
}

function ConnectionPanel({
  disabled,
  onConnected
}: {
  disabled: boolean;
  onConnected: (label: string) => void;
}) {
  const [dbType, setDbType] = useState<DbType>("sqlite");
  const [form, setForm] = useState<ConnectionConfig>({
    db_type: "sqlite",
    sqlite_file_path: "data/demo.db",
    host: "localhost",
    port: 5432
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function update(type: DbType) {
    setDbType(type);
    setForm((current) => ({
      ...current,
      db_type: type,
      port: type === "mysql" ? 3306 : type === "postgresql" ? 5432 : current.port
    }));
  }

  async function submit() {
    setLoading(true);
    setError(null);
    setMessage(null);
    const response = await connectDatabase({ ...form, db_type: dbType });
    setLoading(false);
    if (response.error) {
      setError(response.error);
      return;
    }
    setMessage(response.data?.message ?? "Database connected.");
    onConnected(connectionLabel({ ...form, db_type: dbType }));
  }

  return (
    <Card className="max-w-3xl">
      <div className="mb-5">
        <h2 className="text-lg font-semibold">Database connection</h2>
        <p className="mt-1 text-sm text-slate-500">
          Connect SQLite, PostgreSQL, or MySQL through the existing FastAPI and MCP flow.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Database type">
          <select className={inputClass} value={dbType} onChange={(event) => update(event.target.value as DbType)}>
            <option value="sqlite">SQLite</option>
            <option value="postgresql">PostgreSQL</option>
            <option value="mysql">MySQL</option>
          </select>
        </Field>
        {dbType === "sqlite" ? (
          <Field label="SQLite file path">
            <input
              className={inputClass}
              value={form.sqlite_file_path ?? ""}
              onChange={(event) => setForm({ ...form, sqlite_file_path: event.target.value })}
            />
          </Field>
        ) : (
          <>
            <Field label="Host">
              <input
                className={inputClass}
                value={form.host ?? ""}
                onChange={(event) => setForm({ ...form, host: event.target.value })}
              />
            </Field>
            <Field label="Port">
              <input
                className={inputClass}
                type="number"
                value={form.port ?? ""}
                onChange={(event) => setForm({ ...form, port: Number(event.target.value) })}
              />
            </Field>
            <Field label="Database name">
              <input
                className={inputClass}
                value={form.database_name ?? ""}
                onChange={(event) => setForm({ ...form, database_name: event.target.value })}
              />
            </Field>
            <Field label="Username">
              <input
                className={inputClass}
                value={form.username ?? ""}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
              />
            </Field>
            <Field label="Password">
              <input
                className={inputClass}
                type="password"
                value={form.password ?? ""}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
              />
            </Field>
          </>
        )}
      </div>
      <div className="mt-5 flex items-center gap-3">
        <Button disabled={disabled || loading} onClick={submit}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Connect
        </Button>
        {message && <Badge tone="success">{message}</Badge>}
      </div>
      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}
    </Card>
  );
}

function SchemaCard({
  schema,
  error
}: {
  schema: SchemaResponse | null;
  error: string | null;
}) {
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Database schema</h2>
        <Badge>{schema?.tables.length ?? 0} tables</Badge>
      </div>
      {error && <ErrorBanner message={error} />}
      {!schema?.tables.length ? (
        <p className="text-sm text-slate-500">No schema loaded yet.</p>
      ) : (
        <div className="space-y-2">
          {schema.tables.map((table) => (
            <details key={table.name} className="rounded-lg border border-border bg-slate-50 p-3">
              <summary className="flex cursor-pointer items-center justify-between text-sm font-semibold">
                {table.name}
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </summary>
              <div className="mt-3 space-y-2">
                {table.columns.map((column) => (
                  <div key={column.name} className="flex justify-between gap-3 text-xs">
                    <span className="font-medium text-slate-700">{column.name}</span>
                    <span className="text-slate-500">{column.type}</span>
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
    </Card>
  );
}

function HistoryPanel({ items }: { items: HistoryItem[] }) {
  if (!items.length) {
    return (
      <EmptyState
        title="No history yet"
        message="Questions, analyses, and dashboards generated in this session will appear here."
      />
    );
  }
  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold">Session history</h2>
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={`${item.timestamp}-${index}`} className="rounded-xl border border-border p-4">
            <div className="flex items-center justify-between gap-3">
              <Badge>{item.mode}</Badge>
              <span className="text-xs text-slate-500">{item.timestamp}</span>
            </div>
            <p className="mt-3 text-sm font-medium text-slate-800">{item.prompt}</p>
            {item.rowCount !== undefined && (
              <p className="mt-2 text-xs text-slate-500">{item.rowCount} rows returned</p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function addHistory(
  setHistory: Dispatch<SetStateAction<HistoryItem[]>>,
  mode: HistoryItem["mode"],
  prompt: string,
  rowCount?: number
) {
  setHistory((current) =>
    [
      {
        mode,
        prompt,
        rowCount,
        timestamp: new Date().toLocaleString()
      },
      ...current
    ].slice(0, 25)
  );
}

function connectionLabel(config: ConnectionConfig) {
  if (config.db_type === "sqlite") {
    return `SQLite · ${config.sqlite_file_path ?? "database"}`;
  }
  return `${config.db_type.toUpperCase()} · ${config.database_name ?? "database"}@${
    config.host ?? "host"
  }`;
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function ReportCard({
  eyebrow,
  title,
  markdown
}: {
  eyebrow: string;
  title: string;
  markdown: string;
}) {
  return (
    <Card>
      <div className="mb-5 border-b border-border pb-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-blue-700">
          {eyebrow}
        </div>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-950">
          {title}
        </h2>
      </div>
      <ExecutiveMarkdownReport markdown={normalizeMarkdownReport(markdown)} />
    </Card>
  );
}

function ExecutiveMarkdownReport({ markdown }: { markdown: string }) {
  return (
    <div className="max-w-none text-sm leading-7 text-slate-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 text-2xl font-semibold tracking-tight text-slate-950">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-6 border-t border-border pt-5 text-lg font-semibold tracking-tight text-slate-900 first:mt-0 first:border-t-0 first:pt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-4 text-base font-semibold text-slate-900">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-4 text-slate-600">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="mb-4 ml-5 list-disc space-y-2 text-slate-600">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 ml-5 list-decimal space-y-3 text-slate-600">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-1">{children}</li>,
          table: ({ children }) => (
            <div className="mb-5 overflow-hidden rounded-xl border border-border">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse bg-white text-left text-sm">
                  {children}
                </table>
              </div>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-slate-100 px-4 py-3 align-top text-slate-600">
              {children}
            </td>
          )
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

function normalizeMarkdownReport(markdown: string) {
  const normalized = repairBrokenMarkdownLists(
    markdown
    .replace(/\\n/g, "\n")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^\s*[-*]\s*$/gm, "")
    .replace(/^\s*\d+\.\s*$/gm, "")
    .replace(/^here is (the )?/gim, "")
    .replace(/^Final Insight Report:\s*(.+)$/gim, "# Dashboard Insight Report: $1")
    .replace(/^Final Insight Report$/gim, "# Dashboard Insight Report")
    .replace(/^Summary:\s*$/gim, "## Executive Summary")
    .replace(/^Summary:\s*(.+)$/gim, "## Executive Summary\n$1")
    .replace(/^Key Findings:\s*$/gim, "## Key Findings")
    .replace(/^Recommendations:\s*$/gim, "## Recommendations")
    .replace(/^Attention Areas:\s*$/gim, "## Attention Areas")
    .replace(/^Risks & Follow-ups:\s*$/gim, "## Risks & Follow-ups")
    .replace(/(\*\*[^*\n]+:\*\*)/g, "\n$1")
    .replace(/^\*\*([^*\n]+):\*\*\s*(.+)$/gm, "- **$1:** $2")
    .replace(/^\*\*(Explanation)\*\*$/gim, "## $1")
    .replace(/^\*\*(Final Insight Report)\*\*$/gim, "# $1")
    .replace(/^\*\*(Smart Analysis Report)\*\*$/gim, "# $1")
    .replace(/^\*\*(Dashboard Insight Report)\*\*$/gim, "# $1")
    .replace(/^\*\*(Executive Summary)\*\*$/gim, "## $1")
    .replace(/^\*\*(Key Findings)\*\*$/gim, "## $1")
    .replace(/^\*\*(Supporting Metrics)\*\*$/gim, "## $1")
    .replace(/^\*\*(Recommendations)\*\*$/gim, "## $1")
    .replace(/^\*\*(Attention Areas)\*\*$/gim, "## $1")
    .replace(/^\*\*(KPI Interpretation)\*\*$/gim, "## $1")
    .replace(/^\*\*(Chart Insights)\*\*$/gim, "## $1")
    .replace(/^\*\*(Business \/ Academic Recommendations)\*\*$/gim, "## $1")
    .replace(/^\*\*(Risks & Follow-ups)\*\*$/gim, "## $1")
  )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return removeDuplicateMarkdownTitles(normalized);
}

function repairBrokenMarkdownLists(markdown: string) {
  const lines = markdown.split("\n");
  const repaired: string[] = [];
  let pendingNumber: string | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    const numberMatch = trimmed.match(/^(\d+)\.\s*$/);
    if (numberMatch) {
      pendingNumber = numberMatch[1];
      continue;
    }
    if (!trimmed) {
      continue;
    }
    if (pendingNumber) {
      repaired.push(`${pendingNumber}. ${trimmed}`);
      pendingNumber = null;
      continue;
    }
    repaired.push(line);
  }

  return repaired.join("\n");
}

function removeDuplicateMarkdownTitles(markdown: string) {
  const seen = new Set<string>();
  return markdown
    .split("\n")
    .filter((line) => {
      const title = line.match(/^#{1,2}\s+(.+)$/)?.[1]?.trim().toLowerCase();
      if (!title) return true;
      if (seen.has(title)) return false;
      seen.add(title);
      return true;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function formatKpiValue(value: unknown, title = "") {
  if (value == null || value === "") return "-";
  if (typeof value !== "number") {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return String(value);
    return formatKpiNumber(parsed, title);
  }
  return formatKpiNumber(value, title);
}

function formatKpiNumber(value: number, title: string) {
  const percentage = isPercentageKpi(title);
  const suffix = percentage ? "%" : "";
  const absolute = Math.abs(value);
  const displayValue =
    !percentage && absolute >= 1_000_000
      ? `${trimTrailingZeros(value / 1_000_000)}M`
      : !percentage && absolute >= 10_000
        ? `${trimTrailingZeros(value / 1_000)}K`
        : trimTrailingZeros(value);
  return `${displayValue}${suffix}`;
}

function trimTrailingZeros(value: number) {
  return value.toFixed(2).replace(/\.?0+$/, "");
}

function isPercentageKpi(title: string) {
  return /percent|percentage|rate|ratio|attendance|accuracy|completion|conversion|margin/i.test(
    title
  );
}
