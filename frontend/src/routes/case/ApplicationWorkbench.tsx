import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileText, Gavel, Plus, Send } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const STATUS_VARIANT: Record<string, any> = {
  not_started: "slate", in_progress: "warning", complete: "success",
  draft: "slate", in_prep: "warning", ready: "success", filed: "success",
};

const FS_KINDS = [
  "income_statement","balance_sheet","cash_flow","rate_base","capex","om","custom"
];

export default function ApplicationWorkbench() {
  const { caseId, caseData } = useCaseContext();
  const qc = useQueryClient();
  const snapQ = useQuery({ queryKey: ["aw", caseId, "snapshot"], queryFn: () => api.getWorkbenchSnapshot(caseId) });

  const fileMut = useMutation({
    mutationFn: () => api.fileApplication(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aw", caseId] }),
  });
  const initPkgMut = useMutation({
    mutationFn: () => api.upsertApplicationPackage(caseId, { title: `${caseData?.name ?? "Case"} — application package` }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aw", caseId] }),
  });

  if (snapQ.isLoading) return <Skeleton className="m-6 h-96" />;
  const snap = snapQ.data;
  if (!snap) return null;

  return (
    <>
      <PageHeader
        eyebrow={<>Pre-filing</>}
        title="Application Workbench"
        description="Assemble the pre-filing package: financial schedules, cost-of-service studies, rate-design proposals, and expert testimony lineup. Lock to file when all components are complete."
        actions={
          <div className="flex gap-2">
            {!snap.package && (
              <Button size="sm" onClick={() => initPkgMut.mutate()}>
                <Plus className="h-3.5 w-3.5" /> Create package
              </Button>
            )}
            {snap.package && snap.package.status !== "filed" && (
              <Button size="sm" disabled={!snap.ready_to_file || fileMut.isPending} onClick={() => fileMut.mutate()}>
                <Send className="h-3.5 w-3.5" /> {fileMut.isPending ? "Filing…" : "File application"}
              </Button>
            )}
            {snap.package?.status === "filed" && (
              <Badge variant="success"><CheckCircle2 className="mr-1 h-3 w-3" /> Filed</Badge>
            )}
          </div>
        }
      />
      <div className="p-6 space-y-4">
        {snap.blockers?.length > 0 && (
          <Card className="border-amber-200 bg-amber-50/40">
            <CardContent className="p-3 text-xs">
              <div className="font-semibold text-amber-900 flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5" /> Cannot file yet — {snap.blockers.length} blocker(s)
              </div>
              <ul className="mt-1 list-disc pl-5 text-amber-900">
                {snap.blockers.map((b: string, i: number) => <li key={i}>{b}</li>)}
              </ul>
            </CardContent>
          </Card>
        )}

        <FinancialSchedules caseId={caseId} />
        <CostOfService caseId={caseId} />
        <RateDesign caseId={caseId} />

        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4 text-brand-600" /> Expert testimony lineup
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs">
            <div>{snap.testimony_filed_count} of {snap.testimony_count} testimony pieces filed.</div>
            <a className="text-brand-700 hover:underline" href={`/cases/${caseId}/testimony`}>Go to Testimony Studio →</a>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function FinancialSchedules({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["aw", caseId, "fs"], queryFn: () => api.listFinancialSchedules(caseId) });
  const [name, setName] = useState("");
  const [kind, setKind] = useState("income_statement");
  const createMut = useMutation({
    mutationFn: () => api.createFinancialSchedule({ case_id: caseId, name, kind, status: "not_started" }),
    onSuccess: () => { setName(""); qc.invalidateQueries({ queryKey: ["aw", caseId] }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: any) => api.updateFinancialSchedule(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aw", caseId] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteFinancialSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aw", caseId] }),
  });
  const items = q.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <FileText className="h-4 w-4 text-brand-600" />
          Financial schedules <Badge variant="outline">{items.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Schedule name (e.g. Income Statement 2023-2026)" />
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>{FS_KINDS.map((k) => (<SelectItem key={k} value={k}>{k.replaceAll("_", " ")}</SelectItem>))}</SelectContent>
          </Select>
          <Button size="sm" disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}>Add</Button>
        </div>
        {items.length === 0 && <div className="text-xs text-muted-foreground">None yet</div>}
        {items.map((f: any) => (
          <div key={f.id} className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5">
            <div className="min-w-0">
              <div className="text-sm">{f.name}</div>
              <div className="text-[11px] text-muted-foreground">{f.kind.replaceAll("_", " ")}</div>
            </div>
            <Select value={f.status} onValueChange={(v) => updateMut.mutate({ id: f.id, body: { ...f, status: v } })}>
              <SelectTrigger className="h-7 w-32 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="not_started">Not started</SelectItem>
                <SelectItem value="in_progress">In progress</SelectItem>
                <SelectItem value="complete">Complete</SelectItem>
              </SelectContent>
            </Select>
            <Button size="sm" variant="outline" onClick={() => deleteMut.mutate(f.id)}>×</Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function CostOfService({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["aw", caseId, "cos"], queryFn: () => api.listCostOfService(caseId) });
  const [name, setName] = useState("");
  const [studyType, setStudyType] = useState("embedded");
  const createMut = useMutation({
    mutationFn: () => api.createCostOfService({ case_id: caseId, name, study_type: studyType, source_uc_tables: [], status: "in_progress" }),
    onSuccess: () => { setName(""); qc.invalidateQueries({ queryKey: ["aw", caseId] }); },
  });
  const items = q.data ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Cost-of-service studies <Badge variant="outline">{items.length}</Badge></CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Study name (e.g. Embedded COS 2026)" />
          <Select value={studyType} onValueChange={setStudyType}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="embedded">Embedded</SelectItem>
              <SelectItem value="MDS">Minimum-distribution-system</SelectItem>
              <SelectItem value="fixed_variable">Fixed-variable</SelectItem>
              <SelectItem value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}>Add</Button>
        </div>
        {items.map((c: any) => (
          <div key={c.id} className="rounded-md border border-slate-200 bg-white px-2.5 py-2">
            <div className="text-sm font-medium">{c.name}</div>
            <div className="text-[11px] text-muted-foreground">{c.study_type} · {c.status}</div>
            {c.summary && <div className="mt-1 text-xs text-slate-700">{c.summary}</div>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function RateDesign({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["aw", caseId, "rd"], queryFn: () => api.listRateDesign(caseId) });
  const [name, setName] = useState("");
  const [impact, setImpact] = useState("");
  const createMut = useMutation({
    mutationFn: () => api.createRateDesign({ case_id: caseId, name, proposed_structure: {}, bill_impact_summary: impact, status: "draft" }),
    onSuccess: () => { setName(""); setImpact(""); qc.invalidateQueries({ queryKey: ["aw", caseId] }); },
  });
  const items = q.data ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Rate design proposals <Badge variant="outline">{items.length}</Badge></CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Proposal name (e.g. 3-tier residential rate)" />
          <Input value={impact} onChange={(e) => setImpact(e.target.value)} placeholder="Bill impact summary" />
        </div>
        <Button size="sm" disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}>Add proposal</Button>
        {items.map((r: any) => (
          <div key={r.id} className="rounded-md border border-slate-200 bg-white px-2.5 py-2">
            <div className="text-sm font-medium">{r.name}</div>
            <div className="text-[11px] text-muted-foreground">{r.status}</div>
            {r.bill_impact_summary && <div className="mt-1 text-xs text-slate-700">{r.bill_impact_summary}</div>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
