import * as XLSX from "xlsx";

export function downloadCsv(rows: Record<string, unknown>[], filename: string) {
  const csv = rowsToCsv(rows);
  downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), filename);
}

export function downloadExcel(rows: Record<string, unknown>[], filename: string) {
  const worksheet = XLSX.utils.json_to_sheet(rows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Results");
  const bytes = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
  downloadBlob(
    new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }),
    filename
  );
}

function rowsToCsv(rows: Record<string, unknown>[]) {
  if (!rows.length) return "";
  const columns = Object.keys(rows[0]);
  const header = columns.join(",");
  const body = rows.map((row) =>
    columns.map((column) => escapeCsv(row[column])).join(",")
  );
  return [header, ...body].join("\n");
}

function escapeCsv(value: unknown) {
  const text = value == null ? "" : String(value);
  if (!/[",\n]/.test(text)) return text;
  return `"${text.split('"').join('""')}"`;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
