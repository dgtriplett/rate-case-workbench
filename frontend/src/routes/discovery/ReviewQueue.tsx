import { useMemo, useState } from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Send,
  ShieldCheck,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { RoleGate } from "@/shell/RoleGate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DiffViewer } from "@/components/DiffViewer";
import {
  DrStatusBadge,
  PriorityBadge,
  ResponseStatusBadge,
} from "@/components/StatusBadges";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate, fmtRelative } from "@/lib/format";
import type { DataRequestOut, ResponseOut } from "@/lib/types";

export default function ReviewQueue() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();

  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });

  // Get DRs that are in review
  const inReview = useMemo(() => {
    return (drsQ.data ?? []).filter(
      (d) => d.status === "in_review" || d.status === "drafting",
    );
  }, [drsQ.data]);

  // Fetch current responses for each DR
  const respQueries = useQueries({
    queries: inReview.map((d) => ({
      queryKey: ["dr", d.id, "response"],
      queryFn: () => api.getCurrentResponse(d.id),
    })),
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  const approveMut = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      api.approveResponse(id, comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
    },
  });

  const submitMut = useMutation({
    mutationFn: (responseId: string) => api.submitResponse(responseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
    },
  });

  return (
    <RoleGate
      anyOf={["reviewer", "approver", "case_manager", "admin"]}
      caseId={caseId}
    >
      <PageHeader
        eyebrow={<>Review</>}
        title="Review queue"
        description="Drafts pending review. Compare to the prior version, run a position check, then approve or request changes."
      />
      <div className="space-y-3 p-6">
        {drsQ.isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        )}

        {!drsQ.isLoading && inReview.length === 0 && (
          <EmptyState
            icon={<CheckCircle2 className="h-4 w-4" />}
            title="No drafts awaiting review."
            description="When draft authors submit responses for review they'll show up here."
          />
        )}

        {inReview.map((d, i) => {
          const resp = respQueries[i]?.data ?? null;
          const isOpen = expanded === d.id;
          return (
            <ReviewCard
              key={d.id}
              dr={d}
              response={resp}
              open={isOpen}
              onToggle={() => setExpanded(isOpen ? null : d.id)}
              onApprove={(comment) =>
                resp && approveMut.mutate({ id: resp.id, comment })
              }
              onSubmit={() => resp && submitMut.mutate(resp.id)}
              caseId={caseId}
            />
          );
        })}
      </div>
    </RoleGate>
  );
}

function ReviewCard({
  dr,
  response,
  open,
  onToggle,
  onApprove,
  onSubmit,
  caseId,
}: {
  dr: DataRequestOut;
  response: ResponseOut | null;
  open: boolean;
  onToggle: () => void;
  onApprove: (comment?: string) => void;
  onSubmit: () => void;
  caseId: string;
}) {
  const [comment, setComment] = useState("");
  const draft = response?.draft_text ?? "";
  const final = response?.final_text ?? "";
  const positionMut = useMutation({
    mutationFn: () => api.positionCheck(caseId, draft),
  });

  return (
    <Card>
      <CardContent className="p-0">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
        >
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700">
              {open ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {dr.dr_number}
                </span>
                <DrStatusBadge status={dr.status} />
                <PriorityBadge priority={dr.priority} />
                {response && <ResponseStatusBadge status={response.status} />}
              </div>
              <div className="mt-0.5 truncate text-sm font-medium text-slate-800">
                {dr.subject}
              </div>
              <div className="text-xs text-muted-foreground">
                {dr.requester} · due {fmtDate(dr.due_date)}
                {response && (
                  <> · v{response.version} updated {fmtRelative(response.updated_at)}</>
                )}
              </div>
            </div>
          </div>
          <Link
            to="/cases/$caseId/discovery/$drId"
            params={{ caseId, drId: dr.id }}
            onClick={(e) => e.stopPropagation()}
          >
            <Button variant="outline" size="sm">
              Open drafter
            </Button>
          </Link>
        </button>

        {open && (
          <div className="border-t border-border px-4 py-3">
            {!response ? (
              <div className="text-sm text-muted-foreground">
                No response on this DR yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Diff (draft vs previous)
                    </h4>
                    <span className="text-[11px] text-muted-foreground">
                      v{response.version}
                    </span>
                  </div>
                  <DiffViewer before={final || ""} after={draft || ""} />
                </div>
                <div className="space-y-3">
                  <div>
                    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      <ShieldCheck className="h-3.5 w-3.5" /> Position check
                    </h4>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => positionMut.mutate()}
                      disabled={positionMut.isPending}
                    >
                      {positionMut.isPending
                        ? "Checking…"
                        : "Run consistency check"}
                    </Button>
                    {positionMut.data && (
                      <div className="mt-2 rounded-md border border-slate-200 bg-white p-2 text-xs">
                        {positionMut.data.warnings.length === 0 ? (
                          <div className="text-emerald-700">
                            Consistent with prior positions.
                          </div>
                        ) : (
                          <ul className="space-y-1">
                            {positionMut.data.warnings.map((w, i) => (
                              <li key={i} className="text-slate-700">
                                <span className="font-medium">
                                  {w.topic_key}:
                                </span>{" "}
                                {w.fact_text}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Reviewer comment
                    </h4>
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Optional comment…"
                      className="min-h-[80px] w-full rounded-md border border-slate-200 bg-white p-2 text-xs"
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button
                      className="flex-1"
                      onClick={() => onApprove(comment || undefined)}
                    >
                      <CheckCheck className="h-3.5 w-3.5" />
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={onSubmit}
                    >
                      <Send className="h-3.5 w-3.5" />
                      Resubmit
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
