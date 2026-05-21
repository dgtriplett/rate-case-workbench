import { CheckCircle2, Circle, Clock, Flag } from "lucide-react";
import { cn } from "@/lib/cn";
import type { PhaseOut } from "@/lib/types";
import { PHASE_LABELS, fmtDate } from "@/lib/format";

interface PhaseTimelineProps {
  phases: PhaseOut[];
}

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> =
  {
    not_started: Circle,
    in_progress: Clock,
    filed: Flag,
    closed: CheckCircle2,
  };

export function PhaseTimeline({ phases }: PhaseTimelineProps) {
  const sorted = [...phases].sort((a, b) => a.sequence - b.sequence);
  return (
    <ol className="relative">
      {sorted.map((p, i) => {
        const Icon = STATUS_ICON[p.status] ?? Circle;
        const active = p.status === "in_progress";
        const done = p.status === "filed" || p.status === "closed";
        return (
          <li
            key={p.id}
            className={cn(
              "relative flex items-start gap-3 pb-5 last:pb-0",
            )}
          >
            {i < sorted.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "absolute left-3 top-7 h-[calc(100%-1rem)] w-px",
                  done ? "bg-brand-300" : "bg-slate-200",
                )}
              />
            )}
            <div
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-white shadow-soft",
                done && "border-brand-500 bg-brand-50",
                active && "border-brand-500 glow-brand",
              )}
            >
              <Icon
                className={cn(
                  "h-3.5 w-3.5",
                  done
                    ? "text-brand-700"
                    : active
                      ? "text-brand-600"
                      : "text-slate-400",
                )}
              />
            </div>
            <div className="-mt-0.5 flex flex-1 items-center justify-between gap-3">
              <div>
                <div
                  className={cn(
                    "text-sm font-medium",
                    active && "text-brand-800",
                  )}
                >
                  {PHASE_LABELS[p.phase_type]}
                </div>
                <div className="text-xs text-muted-foreground">
                  {p.deadline_date
                    ? `Deadline ${fmtDate(p.deadline_date)}`
                    : "No deadline set"}
                </div>
              </div>
              <div className="text-xs text-muted-foreground capitalize">
                {p.status.replaceAll("_", " ")}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
