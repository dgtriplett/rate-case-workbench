import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare, Save, Scale } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";

export default function AljRecommendation() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "alj"], queryFn: () => api.getAljRecommendation(caseId) });
  const cmpQ = useQuery({ queryKey: ["cases", caseId, "alj-cmp"], queryFn: () => api.compareAljVsOrder(caseId) });

  const [draft, setDraft] = useState<any>({ case_id: caseId });
  useEffect(() => { if (q.data) setDraft(q.data); else setDraft({ case_id: caseId }); }, [q.data, caseId]);
  const saveMut = useMutation({
    mutationFn: () => api.upsertAljRecommendation(caseId, { ...draft, case_id: caseId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cases", caseId, "alj"] }); qc.invalidateQueries({ queryKey: ["cases", caseId, "alj-cmp"] }); },
  });

  if (q.isLoading) return <Skeleton className="m-6 h-96" />;
  const fields = [
    { key: "alj_name", label: "ALJ name", type: "text" },
    { key: "issued_date", label: "Recommendation date", type: "date" },
    { key: "recommended_revenue_increase_m", label: "Recommended revenue increase ($M)", type: "number" },
    { key: "recommended_roe_pct", label: "Recommended ROE (%)", type: "number" },
    { key: "recommended_equity_pct", label: "Recommended equity (%)", type: "number" },
    { key: "capex_recommended_m", label: "Recommended capex ($M)", type: "number" },
  ];
  return (
    <>
      <PageHeader
        eyebrow={<>Decision</>}
        title="ALJ recommendation"
        description="Record the ALJ's recommended decision. The commission then accepts, modifies, or rejects this in its final order."
        actions={<Button size="sm" disabled={saveMut.isPending} onClick={() => saveMut.mutate()}><Save className="h-3.5 w-3.5" />{saveMut.isPending ? "Saving…" : "Save"}</Button>}
      />
      <div className="grid grid-cols-12 gap-4 p-6">
        <Card className="col-span-12 md:col-span-7">
          <CardHeader><CardTitle className="text-sm"><Scale className="h-4 w-4 inline text-brand-600" /> Recommendation details</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            {fields.map((f) => (
              <div key={f.key}>
                <label className="text-xs font-medium">{f.label}</label>
                <Input
                  type={f.type}
                  step={f.type === "number" ? "0.01" : undefined}
                  value={(draft[f.key] ?? "") as any}
                  onChange={(e) => setDraft((d: any) => ({ ...d, [f.key]: f.type === "number" && e.target.value ? parseFloat(e.target.value) : e.target.value || null }))}
                />
              </div>
            ))}
            <div className="col-span-2">
              <label className="text-xs font-medium">Summary</label>
              <Textarea
                value={draft.summary ?? ""}
                onChange={(e) => setDraft((d: any) => ({ ...d, summary: e.target.value }))}
                className="min-h-[120px]"
                placeholder="Key holdings, positions adopted, positions rejected."
              />
            </div>
          </CardContent>
        </Card>
        <Card className="col-span-12 md:col-span-5">
          <CardHeader><CardTitle className="text-sm"><GitCompare className="h-4 w-4 inline text-brand-600" /> Three-way comparison</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {cmpQ.data && <>
              <CmpRow label="ROE (%)" req={null} alj={cmpQ.data.alj_recommended.roe_pct} order={cmpQ.data.commission_ordered.roe_pct} />
              <CmpRow label="Revenue increase ($M)" req={null} alj={cmpQ.data.alj_recommended.revenue_increase_m} order={cmpQ.data.commission_ordered.revenue_increase_m} />
              <CmpRow label="Equity (%)" req={null} alj={cmpQ.data.alj_recommended.equity_pct} order={cmpQ.data.commission_ordered.equity_pct} />
              <CmpRow label="Capex ($M)" req={null} alj={cmpQ.data.alj_recommended.capex_m} order={cmpQ.data.commission_ordered.capex_m} />
            </>}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function CmpRow({ label, req, alj, order }: any) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-2">
      <div className="text-xs font-medium text-slate-700">{label}</div>
      <div className="mt-1 grid grid-cols-3 gap-1 text-center text-xs">
        <div className="rounded bg-slate-50 py-1"><div className="text-[10px] text-muted-foreground">Requested</div><div className="font-mono">{req ?? "—"}</div></div>
        <div className="rounded bg-amber-50 py-1"><div className="text-[10px] text-amber-700">ALJ</div><div className="font-mono">{alj ?? "—"}</div></div>
        <div className="rounded bg-emerald-50 py-1"><div className="text-[10px] text-emerald-700">Ordered</div><div className="font-mono">{order ?? "—"}</div></div>
      </div>
    </div>
  );
}
