import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Stamp, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { fmtDate, daysUntil } from "@/lib/format";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_VARIANT: Record<string, any> = {
  not_started: "slate",
  in_progress: "brand",
  filed: "warning",
  accepted: "success",
};

export default function CompliancePage() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "compliance"], queryFn: () => api.listCompliance(caseId) });
  const seedMut = useMutation({
    mutationFn: () => api.seedComplianceFromOrder(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "compliance"] }),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: any) => api.updateCompliance(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "compliance"] }),
  });

  const items = q.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow={<>Compliance</>}
        title="Post-order compliance filings"
        description="Tariff sheets, rate transition notifications, accounting orders, and annual reports owed to the commission after the final order is issued."
        actions={
          <Button variant="outline" size="sm" disabled={seedMut.isPending} onClick={() => seedMut.mutate()}>
            <Wand2 className="h-3.5 w-3.5" />
            {seedMut.isPending ? "Seeding…" : "Auto-seed from order"}
          </Button>
        }
      />
      <div className="space-y-3 p-6">
        {q.isLoading && <Skeleton className="h-48" />}
        {!q.isLoading && items.length === 0 && (
          <EmptyState
            icon={<Stamp className="h-4 w-4" />}
            title="No compliance filings yet"
            description="Click 'Auto-seed from order' to generate the standard set (5 templated filings)."
          />
        )}
        {items.map((f: any) => {
          const d = daysUntil(f.due_date);
          const overdue = d != null && d < 0 && f.status !== "filed" && f.status !== "accepted";
          return (
            <Card key={f.id} className={overdue ? "border-rose-200 bg-rose-50/30" : ""}>
              <CardContent className="flex items-center justify-between gap-4 p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-900">{f.name}</span>
                    <Badge variant={STATUS_VARIANT[f.status] ?? "slate"}>{f.status.replaceAll("_", " ")}</Badge>
                    <Badge variant="outline">{f.kind.replaceAll("_", " ")}</Badge>
                    {overdue && <Badge variant="danger">Overdue</Badge>}
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    Due {fmtDate(f.due_date)}{f.filed_date ? ` · filed ${fmtDate(f.filed_date)}` : ""}{d != null && f.status !== "filed" ? ` · ${d > 0 ? `${d}d to go` : `${Math.abs(d)}d past due`}` : ""}
                  </div>
                </div>
                <Select
                  value={f.status}
                  onValueChange={(v) => updateMut.mutate({ id: f.id, body: { ...f, status: v } })}
                >
                  <SelectTrigger className="h-8 w-36 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="not_started">Not started</SelectItem>
                    <SelectItem value="in_progress">In progress</SelectItem>
                    <SelectItem value="filed">Filed</SelectItem>
                    <SelectItem value="accepted">Accepted</SelectItem>
                  </SelectContent>
                </Select>
                {f.status === "filed" && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}
