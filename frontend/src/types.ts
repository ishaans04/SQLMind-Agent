export type Mode = "ask" | "analysis" | "dashboard" | "connections" | "history";

export type DbType = "sqlite" | "postgresql" | "mysql";

export interface QueryResults {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export interface SchemaResponse {
  tables: SchemaTable[];
}

export interface AskResponse {
  question: string;
  sql: string;
  results: QueryResults;
  explanation: string;
}

export interface AnalysisStep {
  step_title: string;
  purpose: string;
  sql_query: string;
}

export interface ExecutedAnalysisStep extends AnalysisStep {
  success: boolean;
  results?: QueryResults | null;
  error?: string | null;
}

export interface AnalysisResponse {
  question: string;
  analysis_plan: AnalysisStep[];
  executed_steps: ExecutedAnalysisStep[];
  result_summaries: string[];
  chart_suggestions: string[];
  final_insight_report: string;
}

export interface DashboardWidget {
  title: string;
  purpose: string;
  sql_query: string;
  success: boolean;
  results?: QueryResults | null;
  value?: unknown;
  error?: string | null;
}

export interface DashboardSqlItem {
  widget_type: "kpi" | "chart" | "table";
  title: string;
  sql_query: string;
  success: boolean;
  error?: string | null;
}

export interface DashboardResponse {
  prompt: string;
  dashboard_title: string;
  kpis: DashboardWidget[];
  charts: DashboardWidget[];
  tables: DashboardWidget[];
  generated_sql: DashboardSqlItem[];
  final_insight_report: string;
}

export interface ConnectionConfig {
  db_type: DbType;
  sqlite_file_path?: string;
  host?: string;
  port?: number;
  database_name?: string;
  username?: string;
  password?: string;
}

export interface HistoryItem {
  mode: "Ask" | "Smart Analysis" | "Dashboard";
  prompt: string;
  timestamp: string;
  rowCount?: number;
}
