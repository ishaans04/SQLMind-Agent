import { Download, FileSpreadsheet } from "lucide-react";

import { downloadCsv, downloadExcel } from "../lib/export";
import type { QueryResults } from "../types";
import { Button } from "./ui";

export function ExportButtons({
  results,
  filename
}: {
  results?: QueryResults | null;
  filename: string;
}) {
  const rows = results?.rows ?? [];
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        disabled={!rows.length}
        onClick={() => downloadCsv(rows, `${filename}.csv`)}
      >
        <Download className="h-4 w-4" />
        CSV
      </Button>
      <Button
        variant="secondary"
        disabled={!rows.length}
        onClick={() => downloadExcel(rows, `${filename}.xlsx`)}
      >
        <FileSpreadsheet className="h-4 w-4" />
        Excel
      </Button>
    </div>
  );
}
