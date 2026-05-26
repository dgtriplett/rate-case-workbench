import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Handshake, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate } from "@/lib/format";

const STATUS_VARIANT: Record<string, any> = {
  proposed: "warning", accepted: "success", rejected: "danger", filed: "info",
};

export default function Settlements() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "settlements"], queryFn: () => api.listSettlements(caseId) });
  const [summary, setSummary] = useState("");
  const [parties, setParties] = useState("");
  const [rev, setRev] = useState("");
  const [roe, setRoe] = useState("");
  const createMut = useMutation({
    mutationFn: () => api.createSettlement({
      case_id: caseId, summary,
      parties: parties.split(",").map((p) => p.trim()).filter(Boolean),
      proposed_revenue_increase_m: rev ? parseFloat(rev) : null,
      proposed_roe_pct: roe ? parseFloat(roe) : null,
      status: "proposed",
      proposed_date: new Date().toISOString().slice(0, 10),
    }),
    onSuccess: () => { setSummary(""); setParties(""); setRev(""); setRoe(""); qc.invalidateQueries({ queryKey: ["cases", caseId, "settlements"] }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: any) => api.updateSettlement(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "settlements"] }),
  });
  const items = q.data ?? [];
  return (
    <>
      <PageHeader
        eyebrow={<>Negotiation</>}
        title="Settlements"
        description="Track settlement offers, signatories, terms, and the commission's disposition."
      />
      <div className="p-6 space-y-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Propose a settlement</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="One-line summary" />
            <div className="grid grid-cols-3 gap-2">
              <Input value={parties} onChange={(e) => setParties(e.target.value)} placeholder="Parties (comma separated)" />
              <Input type="number" step="0.1" value={rev} onChange={(e) => setRev(e.target.value)} placeholder="Revenue increase ($M)" />
              <Input type="number" step="0.01" value={roe} onChange={(e) => setRoe(e.target.value)} placeholder="ROE (%)" />
            </div>
            <Button disabled={!summary || createMut.isPending} onClick={() => createMut.mutate()}><Plus className="h-3.5 w-3.5" /> Add settlement</Button>
          </CardContent>
        </Card>
        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && items.length === 0 && (
          <EmptyState icon={<Handshake className="h-4 w-4" />} title="No settlements yet" description="Settlements proposed during the negotiation phase will appear here." />
        )}
        {items.map((s: any) => (
          <Card key={s.id}>
            <CardContent className="space-y-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-medium">{s.summary}</div>
                <div className="flex items-center gap-2">
                  <Badge variant={STATUS_VARIANT[s.status] ?? "slate"}>{s.status}</Badge>
                  <Select value={s.status} onValueChange={(v) => updateMut.mutate({ id: s.id, body: { ...s, status: v, decision_date: v !== "proposed" ? new Date().toISOString().slice(0, 10) : s.decision_date } })}>
                    <SelectTrigger className="h-7 w-32 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="proposed">Proposed</SelectItem>
                      <SelectItem value="accepted">Accepted</SelectItem>
                      <SelectItem value="rejected">Rejected</SelectItem>
                      <SelectItem value="filed">Filed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                {s.proposed_date && <span>Proposed {fmtDate(s.proposed_date)}</span>}
                {s.decision_date && <span>· Decision {fmtDate(s.decision_date)}</span>}
                {s.proposed_revenue_increase_m != null && <span>· ${s.proposed_revenue_increase_m}M</span>}
                {s.proposed_roe_pct != null && <span>· ROE {s.proposed_roe_pct}%</span>}
              </div>
              {s.parties?.length > 0 && (
                <div className="flex flex-wrap gap-1">{s.parties.map((p: string) => <Badge key={p} variant="outline">{p}</Badge>)}</div>
              )}
              {s.full_text && <div className="text-xs text-slate-700 whitespace-pre-wrap">{s.full_text}</div>}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
