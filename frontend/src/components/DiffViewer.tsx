import { useMemo } from "react";
import { cn } from "@/lib/cn";

interface DiffViewerProps {
  before: string;
  after: string;
}

interface Diff {
  type: "equal" | "insert" | "delete";
  text: string;
}

/** Simple line-based diff that's good enough for review UI. */
function diffLines(a: string, b: string): Diff[] {
  const aLines = a.split("\n");
  const bLines = b.split("\n");
  const m = aLines.length;
  const n = bLines.length;

  // LCS DP — fine for moderate-size drafts.
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array(n + 1).fill(0),
  );
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (aLines[i] === bLines[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const out: Diff[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (aLines[i] === bLines[j]) {
      out.push({ type: "equal", text: aLines[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "delete", text: aLines[i] });
      i++;
    } else {
      out.push({ type: "insert", text: bLines[j] });
      j++;
    }
  }
  while (i < m) out.push({ type: "delete", text: aLines[i++] });
  while (j < n) out.push({ type: "insert", text: bLines[j++] });
  return out;
}

export function DiffViewer({ before, after }: DiffViewerProps) {
  const diffs = useMemo(() => diffLines(before || "", after || ""), [
    before,
    after,
  ]);
  return (
    <div className="rounded-md border border-slate-200 bg-white font-mono text-xs">
      {diffs.map((d, i) => (
        <div
          key={i}
          className={cn(
            "flex items-start gap-2 border-b border-slate-100 px-3 py-1 last:border-0",
            d.type === "insert" && "bg-emerald-50 text-emerald-900",
            d.type === "delete" && "bg-rose-50 text-rose-900",
          )}
        >
          <span
            className={cn(
              "w-4 select-none text-center text-slate-400",
              d.type === "insert" && "text-emerald-600",
              d.type === "delete" && "text-rose-600",
            )}
          >
            {d.type === "insert" ? "+" : d.type === "delete" ? "−" : " "}
          </span>
          <span className="whitespace-pre-wrap break-words">
            {d.text || " "}
          </span>
        </div>
      ))}
    </div>
  );
}
