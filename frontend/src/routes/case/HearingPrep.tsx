import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Gavel, Loader2, Sparkles, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate } from "@/lib/format";

const DIFFICULTY_VARIANT: Record<string, any> = {
  easy: "slate",
  moderate: "warning",
  hard: "danger",
};

export default function HearingPrep() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const [selectedHearing, setSelectedHearing] = useState<string | undefined>();
  const [selectedWitness, setSelectedWitness] = useState<string | undefined>();

  const hearingsQ = useQuery({ queryKey: ["cases", caseId, "hearings"], queryFn: () => api.listHearings(caseId) });
  const witnessesQ = useQuery({ queryKey: ["cases", caseId, "witnesses"], queryFn: () => api.listWitnesses(caseId) });
  const qaQ = useQuery({
    queryKey: ["cases", caseId, "cross-exam", selectedHearing, selectedWitness],
    queryFn: () => api.listCrossExamQA(caseId, selectedHearing, selectedWitness),
  });

  const generateMut = useMutation({
    mutationFn: () => api.generateCrossExamQA({
      case_id: caseId,
      hearing_id: selectedHearing!,
      witness_id: selectedWitness!,
      max_questions: 8,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "cross-exam"] }),
  });
  const markMut = useMutation({
    mutationFn: (id: string) => api.markPracticed(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "cross-exam"] }),
  });

  const hearings = hearingsQ.data ?? [];
  const witnesses = witnessesQ.data ?? [];
  const qa = qaQ.data ?? [];
  const canGen = !!selectedHearing && !!selectedWitness;

  return (
    <>
      <PageHeader
        eyebrow={<>Hearing prep</>}
        title="Cross-examination Q&A bank"
        description="AI-generated likely cross-exam questions per witness per hearing — with grounded proposed answers and source citations. Mark each one practiced as you drill the witness."
      />
      <div className="space-y-4 p-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Select hearing + witness</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Select value={selectedHearing} onValueChange={setSelectedHearing}>
              <SelectTrigger><SelectValue placeholder="Pick a hearing…" /></SelectTrigger>
              <SelectContent>
                {hearings.map((h: any) => (
                  <SelectItem key={h.id} value={h.id}>
                    {h.title} {h.hearing_date ? `· ${fmtDate(h.hearing_date)}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedWitness} onValueChange={setSelectedWitness}>
              <SelectTrigger><SelectValue placeholder="Pick a witness…" /></SelectTrigger>
              <SelectContent>
                {witnesses.map((w: any) => (
                  <SelectItem key={w.id} value={w.id}>{w.name} — {w.title || ""}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={() => generateMut.mutate()} disabled={!canGen || generateMut.isPending}>
              {generateMut.isPending ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Generating…</> : <><Sparkles className="h-3.5 w-3.5" />Generate Q&A with AI</>}
            </Button>
          </CardContent>
        </Card>

        {qaQ.isLoading && <Skeleton className="h-48" />}
        {!qaQ.isLoading && qa.length === 0 && (
          <EmptyState
            icon={<Gavel className="h-4 w-4" />}
            title="No Q&A yet"
            description="Pick a hearing + witness above and click Generate."
          />
        )}
        {qa.map((q: any) => (
          <Card key={q.id} className={q.is_practiced ? "opacity-70" : ""}>
            <CardContent className="space-y-2 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant="brand">{q.topic}</Badge>
                  <Badge variant={DIFFICULTY_VARIANT[q.difficulty] ?? "slate"}>{q.difficulty}</Badge>
                  {q.likely_questioner && <Badge variant="outline">From: {q.likely_questioner}</Badge>}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => markMut.mutate(q.id)}
                  disabled={q.is_practiced}
                >
                  {q.is_practiced ? <><CheckCircle2 className="h-3 w-3 text-emerald-600" />Practiced</> : "Mark practiced"}
                </Button>
              </div>
              <div className="rounded-md border border-amber-200 bg-amber-50/40 p-2.5 text-sm">
                <div className="text-[10px] uppercase tracking-wide text-amber-700">Question</div>
                <div className="mt-0.5 text-slate-800">{q.question}</div>
              </div>
              <div className="rounded-md border border-emerald-200 bg-emerald-50/40 p-2.5 text-sm">
                <div className="text-[10px] uppercase tracking-wide text-emerald-700">Proposed answer</div>
                <div className="mt-0.5 whitespace-pre-wrap text-slate-800">{q.proposed_answer}</div>
                {q.source_citation && <div className="mt-1 text-[11px] text-muted-foreground">Source: {q.source_citation}</div>}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
