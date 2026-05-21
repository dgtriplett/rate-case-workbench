import { useMemo } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  History as HistoryIcon,
  Info,
  Lightbulb,
} from "lucide-react";
import { cn } from "@/lib/cn";
import type { MemoryOut, PositionWarning } from "@/lib/types";
import { Badge } from "./ui/badge";

interface Props {
  warnings: PositionWarning[];
  memories?: MemoryOut[];
  loading?: boolean;
  emptyMessage?: string;
}

const SEVERITY_STYLE: Record<
  PositionWarning["severity"],
  { icon: typeof Info; cls: string; tone: string }
> = {
  info: {
    icon: Info,
    cls: "border-sky-200 bg-sky-50/70",
    tone: "text-sky-700",
  },
  warning: {
    icon: Lightbulb,
    cls: "border-amber-200 bg-amber-50/70",
    tone: "text-amber-700",
  },
  conflict: {
    icon: AlertTriangle,
    cls: "border-rose-200 bg-rose-50/70",
    tone: "text-rose-700",
  },
};

export function PositionConsistencyRail({
  warnings,
  memories = [],
  loading,
  emptyMessage = "No position conflicts detected with the current draft.",
}: Props) {
  const conflicts = warnings.filter((w) => w.severity === "conflict");
  const grouped = useMemo(() => {
    const order: PositionWarning["severity"][] = [
      "conflict",
      "warning",
      "info",
    ];
    return order
      .map((sev) => ({
        sev,
        items: warnings.filter((w) => w.severity === sev),
      }))
      .filter((g) => g.items.length);
  }, [warnings]);

  return (
    <div className="space-y-3">
      {!loading && warnings.length === 0 ? (
        <div className="flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50/60 p-3 text-emerald-700">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="text-xs leading-relaxed">
            <div className="font-medium">Consistent with prior positions</div>
            <div className="opacity-80">{emptyMessage}</div>
          </div>
        </div>
      ) : null}

      {conflicts.length > 0 && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-rose-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            {conflicts.length} contradiction
            {conflicts.length === 1 ? "" : "s"} found with stored positions.
            Recommend review before approval.
          </div>
        </div>
      )}

      <div className="space-y-2">
        {grouped.map((g) => (
          <div key={g.sev} className="space-y-1.5">
            <div className="px-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              {g.sev}
            </div>
            {g.items.map((w, i) => {
              const sty = SEVERITY_STYLE[w.severity];
              const Icon = sty.icon;
              return (
                <div
                  key={`${w.topic_key}-${i}`}
                  className={cn(
                    "rounded-md border p-2.5 text-xs leading-snug",
                    sty.cls,
                  )}
                >
                  <div
                    className={cn(
                      "mb-1 flex items-center gap-1.5 font-medium",
                      sty.tone,
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {w.topic_key}
                  </div>
                  <div className="text-slate-700">{w.fact_text}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {w.source_label}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {memories.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <div className="px-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            Stored positions
          </div>
          {memories.slice(0, 6).map((m) => (
            <div
              key={m.id}
              className="rounded-md border border-slate-200 bg-white p-2.5 text-xs"
            >
              <div className="mb-1 flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-medium text-slate-700">
                  <HistoryIcon className="h-3 w-3 text-brand-600" />
                  {m.topic_key}
                </div>
                <Badge variant="outline" className="text-[10px]">
                  conf. {(m.confidence * 100).toFixed(0)}%
                </Badge>
              </div>
              <p className="text-slate-700">{m.fact_text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
