import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, Loader2, ListChecks, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Verdict = "pass" | "needs_attention" | "fail" | "unable_to_assess";

const VERDICT: Record<
  Verdict,
  { icon: React.ComponentType<{ className?: string }>; cls: string; label: string }
> = {
  pass: { icon: CheckCircle2, cls: "text-emerald-600 bg-emerald-50 ring-emerald-200", label: "Pass" },
  needs_attention: { icon: AlertTriangle, cls: "text-amber-700 bg-amber-50 ring-amber-200", label: "Needs attention" },
  fail: { icon: XCircle, cls: "text-rose-600 bg-rose-50 ring-rose-200", label: "Fail" },
  unable_to_assess: { icon: HelpCircle, cls: "text-slate-500 bg-slate-50 ring-slate-200", label: "Not assessed" },
};

export function ChecklistPanel({
  kind,
  targetId,
  text,
  caseId,
  onApplyAddendum,
}: {
  kind: "response" | "testimony";
  targetId?: string;
  text?: string;
  caseId?: string;
  /** Called when the user clicks "Apply" on a suggested addendum. The string
   *  is the addendum text — the caller is responsible for appending it to
   *  the draft and re-rendering. */
  onApplyAddendum?: (addendum: string) => void;
}) {
  const itemsQ = useQuery({
    queryKey: ["checklist", kind, "items"],
    queryFn: () => api.getChecklist(kind),
  });

  const evalMut = useMutation({
    mutationFn: () =>
      api.evaluateChecklist({ kind, target_id: targetId, text, case_id: caseId }),
  });

  const items = itemsQ.data?.items ?? [];
  const results = evalMut.data?.items ?? [];

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-3.5 py-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
          <ListChecks className="h-3.5 w-3.5 text-brand-600" />
          Best-practices checklist
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => evalMut.mutate()}
          disabled={evalMut.isPending || (!text && !targetId)}
        >
          {evalMut.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Evaluating…
            </>
          ) : results.length > 0 ? (
            "Re-evaluate"
          ) : (
            "Run evaluation"
          )}
        </Button>
      </div>
      <div className="max-h-[360px] overflow-y-auto px-3 py-2 space-y-2">
        {items.length === 0 && itemsQ.isLoading && (
          <div className="px-2 py-3 text-center text-xs text-slate-500">
            Loading checklist…
          </div>
        )}
        {items.map((it) => {
          const result = results.find((r) => r.id === it.id);
          const v = (result?.verdict as Verdict) || "unable_to_assess";
          const cfg = VERDICT[v] || VERDICT.unable_to_assess;
          const Icon = cfg.icon;
          return (
            <div
              key={it.id}
              className="flex items-start gap-2.5 rounded-md border border-slate-100 px-2.5 py-2 hover:bg-slate-50/40"
            >
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-1",
                  cfg.cls,
                )}
                title={cfg.label}
              >
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-slate-800">{it.title}</div>
                {result?.rationale && (
                  <div className="mt-0.5 text-[11px] leading-snug text-slate-500">
                    {result.rationale}
                  </div>
                )}
                {result?.suggested_addendum && onApplyAddendum && (
                  <div className="mt-1.5 rounded-md border border-brand-100 bg-brand-50/60 p-2">
                    <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-brand-700">
                      <Wand2 className="h-3 w-3" /> Suggested addition
                    </div>
                    <div className="line-clamp-3 text-[11px] italic text-slate-700">
                      {result.suggested_addendum}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-1.5 h-6 px-2 text-[10px]"
                      onClick={() => onApplyAddendum(result.suggested_addendum!)}
                    >
                      Apply to draft
                    </Button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {items.length === 0 && !itemsQ.isLoading && (
          <div className="px-2 py-3 text-center text-xs text-slate-500">
            No checklist items configured.
          </div>
        )}
      </div>
    </div>
  );
}
