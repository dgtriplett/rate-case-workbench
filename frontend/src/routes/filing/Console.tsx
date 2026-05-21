import { useMemo } from "react";
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
  FileCheck,
  Gavel,
  Loader2,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { RoleGate } from "@/shell/RoleGate";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate, fmtDateTime } from "@/lib/format";

export default function FilingConsole() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();

  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });

  const approvedDrs = useMemo(
    () => (drsQ.data ?? []).filter((d) => d.status === "approved"),
    [drsQ.data],
  );

  const respQs = useQueries({
    queries: approvedDrs.map((d) => ({
      queryKey: ["dr", d.id, "response"],
      queryFn: () => api.getCurrentResponse(d.id),
    })),
  });

  const fileMut = useMutation({
    mutationFn: (responseId: string) => api.fileResponse(responseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
    },
  });

  return (
    <RoleGate
      anyOf={["case_manager", "approver", "admin"]}
      caseId={caseId}
    >
      <PageHeader
        eyebrow={<>Filing</>}
        title="Filing console"
        description="Approved responses that are ready to be filed with the commission. Filing is an audited action."
      />

      <div className="space-y-3 p-6">
        {drsQ.isLoading && <Skeleton className="h-40" />}

        {!drsQ.isLoading && approvedDrs.length === 0 && (
          <EmptyState
            icon={<FileCheck className="h-4 w-4" />}
            title="Nothing waiting to be filed."
            description="Approved responses ready for filing will appear here."
          />
        )}

        <div className="space-y-2">
          {approvedDrs.map((dr, i) => {
            const resp = respQs[i].data ?? null;
            const filing = fileMut.isPending && fileMut.variables === resp?.id;
            return (
              <Card key={dr.id}>
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">
                        {dr.dr_number}
                      </span>
                      <Badge variant="success">Approved</Badge>
                      {resp && (
                        <Badge variant="outline">v{resp.version}</Badge>
                      )}
                      {resp?.approved_at && (
                        <span className="text-[11px] text-muted-foreground">
                          approved {fmtDateTime(resp.approved_at)}
                        </span>
                      )}
                    </div>
                    <Link
                      to="/cases/$caseId/discovery/$drId"
                      params={{ caseId, drId: dr.id }}
                      className="block truncate text-sm font-medium text-slate-800 hover:text-brand-800"
                    >
                      {dr.subject}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      {dr.requester} · due {fmtDate(dr.due_date)}
                    </div>
                  </div>
                  <Button
                    disabled={!resp || filing}
                    onClick={() => resp && fileMut.mutate(resp.id)}
                  >
                    {filing ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Filing…
                      </>
                    ) : (
                      <>
                        <Gavel className="h-3.5 w-3.5" />
                        File response
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {fileMut.isSuccess && (
          <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            <CheckCheck className="h-4 w-4" />
            Response filed. The commission portal has been notified.
          </div>
        )}
      </div>
    </RoleGate>
  );
}
