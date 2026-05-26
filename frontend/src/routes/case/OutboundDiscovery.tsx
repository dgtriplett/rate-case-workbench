import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightFromLine, Plus } from "lucide-react";
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
import { DrStatusBadge, PriorityBadge } from "@/components/StatusBadges";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate } from "@/lib/format";

export default function OutboundDiscovery() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const drsQ = useQuery({
    queryKey: ["cases", caseId, "outbound-drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId, direction: "outbound" } as any),
  });
  const partiesQ = useQuery({ queryKey: ["cases", caseId, "parties"], queryFn: () => api.listParties(caseId) });

  const [drNumber, setDrNumber] = useState("");
  const [targetParty, setTargetParty] = useState<string | undefined>();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [issued, setIssued] = useState(new Date().toISOString().slice(0, 10));
  const [due, setDue] = useState(new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10));

  const createMut = useMutation({
    mutationFn: () => api.createDataRequest({
      case_id: caseId,
      dr_number: drNumber,
      requester: "NLPG (Utility)",
      requester_kind: "utility",
      subject,
      body,
      issued_date: issued,
      due_date: due,
      priority: "normal",
      topic_tags: [],
      direction: "outbound",
      target_party_id: targetParty,
    } as any),
    onSuccess: () => {
      setDrNumber(""); setSubject(""); setBody("");
      qc.invalidateQueries({ queryKey: ["cases", caseId, "outbound-drs"] });
    },
  });

  const drs = drsQ.data ?? [];
  const parties = (partiesQ.data ?? []).filter((p: any) => p.kind !== "utility");
  const partyById = useMemo(() => Object.fromEntries(parties.map((p: any) => [p.id, p])), [parties]);

  return (
    <>
      <PageHeader
        eyebrow={<>Counter-discovery</>}
        title="Outbound discovery"
        description="Data requests YOU issue against intervenor witnesses. Same drafter / review / file workflow as inbound DRs — just reversed direction."
      />
      <div className="p-6 space-y-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Issue a new outbound DR</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Input value={drNumber} onChange={(e) => setDrNumber(e.target.value)} placeholder="DR number (e.g. NLPG-DR-OCA-001)" />
              <Select value={targetParty} onValueChange={setTargetParty}>
                <SelectTrigger><SelectValue placeholder="Target party" /></SelectTrigger>
                <SelectContent>
                  {parties.map((p: any) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <Input type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />
              <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" />
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[100px]" placeholder="DR body — questions, document requests, time period covered, etc." />
            <Button disabled={!drNumber || !subject || !body || !targetParty || createMut.isPending} onClick={() => createMut.mutate()}>
              <Plus className="h-3.5 w-3.5" /> Issue DR
            </Button>
          </CardContent>
        </Card>

        {drsQ.isLoading && <Skeleton className="h-32" />}
        {!drsQ.isLoading && drs.length === 0 && (
          <EmptyState icon={<ArrowRightFromLine className="h-4 w-4" />} title="No outbound DRs yet" description="Issue your first counter-discovery DR against an intervenor witness above." />
        )}
        {drs.map((d: any) => (
          <Card key={d.id}>
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">{d.dr_number}</span>
                <DrStatusBadge status={d.status} />
                <PriorityBadge priority={d.priority} />
                {d.target_party_id && partyById[d.target_party_id] && (
                  <Badge variant="violet">→ {partyById[d.target_party_id].name}</Badge>
                )}
              </div>
              <div className="mt-1 text-sm font-medium text-slate-800">{d.subject}</div>
              <div className="text-[11px] text-muted-foreground">Issued {fmtDate(d.issued_date)} · due {fmtDate(d.due_date)}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
