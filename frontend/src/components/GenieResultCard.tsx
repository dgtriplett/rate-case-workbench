import { Sparkles, Pin, Database } from "lucide-react";
import { Badge } from "./ui/badge";

interface GenieResult {
  id: string;
  question: string;
  sql?: string;
  rows: Record<string, unknown>[];
  pinned?: boolean;
  source_room?: string;
}

interface GenieResultCardProps {
  result: GenieResult;
  onPinToggle?: (id: string) => void;
}

export function GenieResultCard({
  result,
  onPinToggle,
}: GenieResultCardProps) {
  const columns =
    result.rows.length > 0 ? Object.keys(result.rows[0]) : [];
  return (
    <div className="rounded-md border border-violet-200 bg-violet-50/40 p-3 text-xs">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-1.5">
          <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-violet-100">
            <Sparkles className="h-3 w-3 text-violet-700" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-medium text-violet-900">
              {result.question}
            </div>
            {result.source_room && (
              <Badge variant="violet" className="mt-1 text-[10px]">
                <Database className="h-2.5 w-2.5" />
                {result.source_room}
              </Badge>
            )}
          </div>
        </div>
        {onPinToggle && (
          <button
            onClick={() => onPinToggle(result.id)}
            className="rounded p-1 text-violet-700 hover:bg-violet-100"
            title={result.pinned ? "Unpin" : "Pin"}
          >
            <Pin
              className={`h-3 w-3 ${result.pinned ? "fill-violet-700" : ""}`}
            />
          </button>
        )}
      </div>

      {result.sql && (
        <details className="mb-2">
          <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-violet-700">
            SQL
          </summary>
          <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-[10px] text-slate-700">
            {result.sql}
          </pre>
        </details>
      )}

      {result.rows.length > 0 && (
        <div className="overflow-x-auto rounded border border-violet-200 bg-white">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-violet-200 bg-violet-50/60">
                {columns.map((c) => (
                  <th
                    key={c}
                    className="px-2 py-1 text-left font-medium text-violet-900"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.slice(0, 5).map((r, i) => (
                <tr key={i} className="border-b border-violet-100 last:border-0">
                  {columns.map((c) => (
                    <td key={c} className="px-2 py-1 text-slate-700">
                      {String(r[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
