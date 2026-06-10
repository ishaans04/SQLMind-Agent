import axios from "axios";

import type {
  AnalysisResponse,
  AskResponse,
  ConnectionConfig,
  DashboardResponse,
  SchemaResponse
} from "../types";

const FALLBACK_API_BASE_URL = "http://127.0.0.1:8001";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || FALLBACK_API_BASE_URL
).replace(/\/$/, "");

export const API_BASE_URL_SOURCE = import.meta.env.VITE_API_BASE_URL?.trim()
  ? "frontend/.env"
  : "fallback";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000
});

function detail(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const responseDetail = error.response?.data?.detail;
    if (typeof responseDetail === "string") return responseDetail;
    if (responseDetail) return JSON.stringify(responseDetail);
    return error.message;
  }
  return error instanceof Error ? error.message : "Unexpected request error.";
}

export async function getHealth() {
  try {
    const response = await api.get<{ status: string }>("/health", { timeout: 5000 });
    return { ok: response.data.status === "ok", message: "Backend connected" };
  } catch (error) {
    return { ok: false, message: detail(error) };
  }
}

export async function getSchema() {
  try {
    const response = await api.get<SchemaResponse>("/schema");
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: detail(error) };
  }
}

export async function connectDatabase(config: ConnectionConfig) {
  try {
    const response = await api.post("/connect-database", compact(config));
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: detail(error) };
  }
}

export async function ask(question: string, limit: number) {
  try {
    const response = await api.post<AskResponse>("/ask", { question, limit });
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: detail(error) };
  }
}

export async function analyze(question: string, limit: number) {
  try {
    const response = await api.post<AnalysisResponse>("/analyze", { question, limit });
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: detail(error) };
  }
}

export async function dashboard(prompt: string, limit: number) {
  try {
    const response = await api.post<DashboardResponse>("/dashboard", { prompt, limit });
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: detail(error) };
  }
}

function compact<T extends object>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined && entry !== "")
  ) as Partial<T>;
}
