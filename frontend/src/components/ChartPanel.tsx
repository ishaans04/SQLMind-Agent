import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { buildChartSpec } from "../lib/chart";
import type { QueryResults } from "../types";

const COLORS = ["#2563eb", "#10b981", "#f59e0b", "#7c3aed", "#ef4444", "#0891b2"];

export function ChartPanel({ results }: { results?: QueryResults | null }) {
  const spec = buildChartSpec(results);

  if (spec.kind === "none" || !spec.xKey || !spec.yKey) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
        {spec.message ?? "No chart available for this result."}
      </div>
    );
  }

  return (
    <div className="h-80 rounded-xl border border-border bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        {spec.kind === "line" ? (
          <LineChart data={spec.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={spec.xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line dataKey={spec.yKey} stroke="#2563eb" strokeWidth={2} dot />
          </LineChart>
        ) : spec.kind === "pie" ? (
          <PieChart>
            <Tooltip />
            <Pie
              data={spec.data}
              dataKey={spec.yKey}
              nameKey={spec.xKey}
              outerRadius={105}
              label
            >
              {spec.data.map((_, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={spec.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={spec.xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey={spec.yKey} fill="#2563eb" radius={[6, 6, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
