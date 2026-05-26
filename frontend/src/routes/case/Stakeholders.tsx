import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate } from "@/lib/format";

const KIND_VARIANT: Record<string, any> = {
  utility: "brand", staff: "info", consumer_advocate: "warning",
  industrial: "violet", environmental: "success", individual: "slate", other: "slate",
};

export default function Stakeholders() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "parties"], queryFn: () => api.listParties(caseId) });
  const [name, setName] = useState("");
  const [kind, setKind] = useState("staff");
  const [counsel, setCounsel] = useState("");
  const [counselFirm, setCounselFirm] = useState("");
  const [interventionDate, setInterventionDate] = useState("");
  const createMut = useMutation({
    mutationFn: () => api.createParty({
      case_id: caseId, name, kind,
      counsel_name: counsel || null,
      counsel_firm: counselFirm || null,
      intervention_date: interventionDate || null,
    }),
    onSuccess: () => { setName(""); setCounsel(""); setCounselFirm(""); setInterventionDate(""); qc.invalidateQueries({ queryKey: ["cases", caseId, "parties"] }); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteParty(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "parties"] }),
  });
  const parties = q.data ?? [];
  return (
    <>
      <PageHeader
        eyebrow={<>Stakeholders</>}
        title="Parties & intervention registry"
        description="All parties of record on this case — utility, staff, consumer advocate, intervenors — and their counsel."
      />
      <div className="p-6 space-y-4">
        <Card>
          <CardHeader><CardTitle className="text-sm">Register a new party</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Party name" />
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="utility">Utility</SelectItem>
                <SelectItem value="staff">Commission staff</SelectItem>
                <SelectItem value="consumer_advocate">Consumer advocate</SelectItem>
                <SelectItem value="industrial">Industrial intervenor</SelectItem>
                <SelectItem value="environmental">Environmental intervenor</SelectItem>
                <SelectItem value="individual">Individual</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            <Input value={counsel} onChange={(e) => setCounsel(e.target.value)} placeholder="Counsel name" />
            <Input value={counselFirm} onChange={(e) => setCounselFirm(e.target.value)} placeholder="Firm" />
            <div className="flex gap-1">
              <Input type="date" value={interventionDate} onChange={(e) => setInterventionDate(e.target.value)} />
              <Button size="sm" disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}><Plus className="h-3.5 w-3.5" /></Button>
            </div>
          </CardContent>
        </Card>

        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && parties.length === 0 && (
          <EmptyState icon={<Users className="h-4 w-4" />} title="No parties registered yet" description="Add the utility, commission staff, and any intervenors above." />
        )}
        {parties.map((p: any) => (
          <Card key={p.id}>
            <CardContent className="flex items-center justify-between gap-3 p-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{p.name}</span>
                  <Badge variant={KIND_VARIANT[p.kind] ?? "slate"}>{p.kind.replaceAll("_", " ")}</Badge>
                  {!p.is_active && <Badge variant="slate">inactive</Badge>}
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {p.counsel_name && <>Counsel: <strong>{p.counsel_name}</strong>{p.counsel_firm ? ` (${p.counsel_firm})` : ""}</>}
                  {p.intervention_date && <> · intervened {fmtDate(p.intervention_date)}</>}
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={() => deleteMut.mutate(p.id)}>×</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
