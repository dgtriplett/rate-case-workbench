import { Check } from "lucide-react";
import { cn } from "@/lib/cn";
import type { DRStatus } from "@/lib/types";

const ORDER: DRStatus[] = [
  "new",
  "assigned",
  "drafting",
  "in_review",
  "approved",
  "filed",
];

const LABELS: Record<DRStatus, string> = {
  new: "New",
  assigned: "Assigned",
  drafting: "Drafting",
  in_review: "Review",
  approved: "Approved",
  filed: "Filed",
  objected: "Objected",
};

export function WorkflowStepper({ status }: { status: DRStatus }) {
  if (status === "objected") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
        Objection filed
      </div>
    );
  }
  const currentIdx = ORDER.indexOf(status);
  return (
    <div className="flex items-center gap-1.5">
      {ORDER.map((s, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s} className="flex items-center gap-1.5">
            <div className="flex items-center gap-1.5">
              <div
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold",
                  done && "border-brand-500 bg-brand-500 text-white",
                  active &&
                    "border-brand-500 bg-white text-brand-700 glow-brand",
                  !done &&
                    !active &&
                    "border-slate-200 bg-slate-50 text-slate-400",
                )}
              >
                {done ? <Check className="h-3 w-3" /> : i + 1}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium",
                  active
                    ? "text-brand-800"
                    : done
                      ? "text-slate-700"
                      : "text-slate-400",
                )}
              >
                {LABELS[s]}
              </span>
            </div>
            {i < ORDER.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "h-px w-4",
                  done ? "bg-brand-300" : "bg-slate-200",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
