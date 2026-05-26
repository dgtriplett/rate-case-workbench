import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UserSquare } from "lucide-react";
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

const KIND_VARIANT: Record<string, any> = { direct: "brand", rebuttal: "warning", surrebuttal: "violet" };

export default function IntervenorTestimony() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "inter-testimony"], queryFn: () => api.listIntervenorTestimony(caseId) });
  const partiesQ = useQuery({ queryKey: ["cases", caseId, "parties"], queryFn: () => api.listParties(caseId) });

  const [partyId, setPartyId] = useState<string | undefined>();
  const [witnessName, setWitnessName] = useState("");
  const [kind, setKind] = useState("direct");
  const [title, setTitle] = useState("");
  const [filedDate, setFiledDate] = useState("");
  const [summary, setSummary] = useState("");
  const createMut = useMutation({
    mutationFn: () => api.createIntervenorTestimony({
      case_id: caseId, party_id: partyId, witness_name: witnessName, kind, title,
      filed_date: filedDate || null, summary: summary || null,
    }),
    onSuccess: () => { setWitnessName(""); setTitle(""); setFiledDate(""); setSummary(""); qc.invalidateQueries({ queryKey: ["cases", caseId, "inter-testimony"] }); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteIntervenorTestimony(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "inter-testimony"] }),
  });
  const items = q.data ?? [];
  const parties = partiesQ.data ?? [];
  const partyById = Object.fromEntries(parties.map((p: any) => [p.id, p]));
  return (
    <>
      <PageHeader
        eyebrow={<>Intervenor testimony</>}
        title="Opposing-party testimony filings"
        description="Track the full testimony filings made by other parties on this case. Each one can be paired with intervenor positions and rebutted."
      />
      <div className="p-6 space-y-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Log an intervenor filing</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Select value={partyId} onValueChange={setPartyId}>
                <SelectTrigger><SelectValue placeholder="Party" /></SelectTrigger>
                <SelectContent>{parties.map((p: any) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
              </Select>
              <Input value={witnessName} onChange={(e) => setWitnessName(e.target.value)} placeholder="Witness name" />
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="direct">Direct</SelectItem>
                  <SelectItem value="rebuttal">Rebuttal</SelectItem>
                  <SelectItem value="surrebuttal">Surrebuttal</SelectItem>
                </SelectContent>
              </Select>
              <Input type="date" value={filedDate} onChange={(e) => setFiledDate(e.target.value)} placeholder="Filed date" />
            </div>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Filing title" />
            <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Summary of what's in the filing" />
            <Button disabled={!partyId || !witnessName || !title || createMut.isPending} onClick={() => createMut.mutate()}><Plus className="h-3.5 w-3.5" /> Log filing</Button>
          </CardContent>
        </Card>
        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && items.length === 0 && (
          <EmptyState icon={<UserSquare className="h-4 w-4" />} title="No intervenor testimony logged yet" />
        )}
        {items.map((t: any) => (
          <Card key={t.id}>
            <CardContent className="flex items-center justify-between gap-3 p-3">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant={KIND_VARIANT[t.kind] ?? "slate"}>{t.kind}</Badge>
                  {t.party_id && partyById[t.party_id] && <Badge variant="outline">{partyById[t.party_id].name}</Badge>}
                  {t.filed_date && <span className="text-[11px] text-muted-foreground">filed {fmtDate(t.filed_date)}</span>}
                </div>
                <div className="mt-1 text-sm font-medium">{t.title}</div>
                <div className="text-[11px] text-muted-foreground">{t.witness_name}{t.witness_title ? ` — ${t.witness_title}` : ""}</div>
                {t.summary && <div className="mt-1 text-xs text-slate-700">{t.summary}</div>}
              </div>
              <Button size="sm" variant="outline" onClick={() => deleteMut.mutate(t.id)}>×</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
