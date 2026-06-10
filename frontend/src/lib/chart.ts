import type { QueryResults } from "../types";

export type ChartKind = "bar" | "line" | "pie" | "none";

export interface ChartSpec {
  kind: ChartKind;
  data: Record<string, unknown>[];
  xKey?: string;
  yKey?: string;
  message?: string;
}

export function buildChartSpec(results?: QueryResults | null): ChartSpec {
  const rows = results?.rows ?? [];
  if (!rows.length) return { kind: "none", data: [], message: "No rows to chart." };

  const columns = results?.columns?.length ? results.columns : Object.keys(rows[0]);
  const numericColumns = columns.filter((column) =>
    rows.some((row) => typeof row[column] === "number")
  );
  if (!numericColumns.length) {
    return { kind: "none", data: rows, message: "No numeric columns available." };
  }

  const dateColumn = columns.find((column) => /date|time/i.test(column));
  if (dateColumn) {
    return { kind: "line", data: rows, xKey: dateColumn, yKey: numericColumns[0] };
  }

  const categoryColumns = columns.filter((column) => !numericColumns.includes(column));
  if (categoryColumns.length) {
    const category = categoryColumns[0];
    const numeric = numericColumns[0];
    if (isDistribution(category, numeric, rows)) {
      return { kind: "bar", data: rows, xKey: category, yKey: numeric };
    }
    const uniqueCount = new Set(rows.map((row) => row[category])).size;
    if (uniqueCount <= 5 && rows.length <= 8) {
      return { kind: "pie", data: rows, xKey: category, yKey: numeric };
    }
    return { kind: "bar", data: rows, xKey: category, yKey: numeric };
  }

  if (numericColumns.length === 1) {
    const binned = binNumeric(rows, numericColumns[0]);
    return { kind: "bar", data: binned, xKey: "value_range", yKey: "record_count" };
  }

  return { kind: "bar", data: rows, xKey: numericColumns[0], yKey: numericColumns[1] };
}

function isDistribution(
  categoryColumn: string,
  numericColumn: string,
  rows: Record<string, unknown>[]
) {
  const categoryName = categoryColumn.toLowerCase();
  const numericName = numericColumn.toLowerCase();
  return (
    /bucket|range|bin|label|category/.test(categoryName) ||
    /count|frequency|records|students|rows/.test(numericName) ||
    new Set(rows.map((row) => row[categoryColumn])).size > 5
  );
}

function binNumeric(rows: Record<string, unknown>[], column: string) {
  const values = rows
    .map((row) => Number(row[column]))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    return [{ value_range: String(min), record_count: values.length }];
  }
  const binCount = Math.min(8, Math.max(2, new Set(values).size));
  const width = (max - min) / binCount;
  return Array.from({ length: binCount }, (_, index) => {
    const start = min + index * width;
    const end = index === binCount - 1 ? max : start + width;
    const count = values.filter((value) =>
      index === binCount - 1 ? value >= start && value <= end : value >= start && value < end
    ).length;
    return {
      value_range: `${format(start)}-${format(end)}`,
      record_count: count
    };
  });
}

function format(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
