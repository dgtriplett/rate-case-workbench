import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FilePlus,
  Gavel,
  Link2,
  Plus,
  ScrollText,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate } from "@/lib/format";
import type { IntervenorPosition, TestimonyOut } from "@/lib/types";

const STATUS_VARIANT: Record<IntervenorPosition["status"], any> = {
  open: "warning",
  rebutted: "success",
  accepted: "danger",
  settled: "violet",
};

export default function RebuttalWorkbench() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<IntervenorPosition | null>(null);

  const createRebuttalMut = useMutation({
    mutationFn: async (p: IntervenorPosition) => {
      const title = `Rebuttal — ${p.topic} (${p.intervenor})`;
      const t = await api.createTestimony({
        case_id: caseId,
        kind: "rebuttal",
        title,
        draft_text:
          `REBUTTAL TESTIMONY\n\nRe: ${p.intervenor} — ${p.topic}\n\n` +
          `Q. Please describe the position you are rebutting.\n` +
          `A. ${p.position_text}\n` +
          (p.source_citation ? `(Source: ${p.source_citation})\n` : "") +
          `\nQ. What is the Company's response?\nA. `,
      } as any);
      await api.linkRebuttal(p.id, t.id);
      return t;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "positions"] });
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
      navigate({ to: "/cases/$caseId/testimony", params: { caseId } });
    },
  });

  const positionsQ = useQuery({
    queryKey: ["cases", caseId, "positions"],
    queryFn: () => api.listPositions(caseId),
  });
  const testimonyQ = useQuery({
    queryKey: ["cases", caseId, "testimony"],
    queryFn: () => api.listTestimony(caseId),
  });

  const positions = positionsQ.data ?? [];
  const testimony = testimonyQ.data ?? [];
  const rebuttalTestimony = testimony.filter(
    (t) => t.kind === "rebuttal" || t.kind === "surrebuttal",
  );

  const stats = useMemo(() => {
    return {
      total: positions.length,
      open: positions.filter((p) => p.status === "open").length,
      rebutted: positions.filter((p) => p.status === "rebutted").length,
      totalImpactM: positions.reduce((a, p) => a + (p.impact_amount_m ?? 0), 0),
    };
  }, [positions]);

  const linkMut = useMutation({
    mutationFn: ({ positionId, testimonyId }: { positionId: string; testimonyId: string }) =>
      api.linkRebuttal(positionId, testimonyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "positions"] });
      setSelected(null);
    },
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Rebuttal</>}
        title="Rebuttal workbench"
        description="Track positions taken by intervenors in their direct testimony and link each one to the rebuttal piece that addresses it."
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="warning">{stats.open} open</Badge>
            <Badge variant="success">{stats.rebutted} rebutted</Badge>
            <Badge variant="outline">${stats.totalImpactM.toFixed(1)}M at risk</Badge>
            <NewPositionDialog caseId={caseId} />
          </div>
        }
      />

      <div className="grid grid-cols-12 gap-4 p-6">
        <div className="col-span-12 lg:col-span-7 space-y-3">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Intervenor positions
          </div>
          {positionsQ.isLoading && <Skeleton className="h-64" />}
          {!positionsQ.isLoading && positions.length === 0 && (
            <EmptyState
              icon={<Gavel className="h-4 w-4" />}
              title="No intervenor positions logged yet."
              description="Add a position taken by an intervenor (or pre-populate by uploading their direct testimony to Knowledge)."
            />
          )}
          {positions.map((p) => {
            const linkedT = testimony.find((t) => t.id === p.rebutted_by_testimony_id);
            return (
              <Card
                key={p.id}
                className={`cursor-pointer transition-all hover:shadow-elevated ${
                  selected?.id === p.id ? "ring-2 ring-brand-400" : ""
                }`}
                onClick={() => setSelected(p)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="slate">{p.intervenor}</Badge>
                        <Badge variant={STATUS_VARIANT[p.status]}>{p.status}</Badge>
                        {p.impact_amount_m != null && (
                          <Badge variant="outline">${p.impact_amount_m.toFixed(1)}M</Badge>
                        )}
                      </div>
                      <h3 className="mt-1.5 text-sm font-semibold text-slate-900">
                        {p.topic}
                      </h3>
                      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-600">
                        {p.position_text}
                      </p>
                      {p.source_citation && (
                        <div className="mt-1.5 text-[11px] text-muted-foreground">
                          {p.source_citation}
                          {p.filed_date && <> · filed {fmtDate(p.filed_date)}</>}
                        </div>
                      )}
                      {p.proposed_adjustment && (
                        <div className="mt-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-900">
                          <strong>Proposed adjustment:</strong> {p.proposed_adjustment}
                        </div>
                      )}
                      {linkedT ? (
                        <Link
                          to="/cases/$caseId/testimony"
                          params={{ caseId }}
                          className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-brand-700 hover:underline"
                        >
                          <ScrollText className="h-3 w-3" />
                          Rebutted by: {linkedT.title}
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2 h-7 text-[11px]"
                          onClick={(e) => {
                            e.stopPropagation();
                            createRebuttalMut.mutate(p);
                          }}
                          disabled={createRebuttalMut.isPending}
                        >
                          <FilePlus className="h-3 w-3" />
                          {createRebuttalMut.isPending ? "Creating…" : "Draft rebuttal"}
                        </Button>
                      )}
                    </div>
                    {p.status === "rebutted" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <aside className="col-span-12 lg:col-span-5">
          <div className="sticky top-2 space-y-3">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              {selected ? "Link to rebuttal" : "Select a position to link"}
            </div>
            {!selected ? (
              <Card>
                <CardContent className="flex h-48 items-center justify-center text-center text-xs text-muted-foreground">
                  Click any position on the left to link it to a rebuttal testimony.
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="p-4 space-y-3">
                  <div>
                    <div className="text-xs font-semibold text-slate-800">Position</div>
                    <div className="text-xs text-slate-600 line-clamp-3">{selected.topic}</div>
                  </div>

                  <Button
                    className="w-full"
                    onClick={() => createRebuttalMut.mutate(selected)}
                    disabled={createRebuttalMut.isPending || selected.status === "rebutted"}
                  >
                    <FilePlus className="h-3.5 w-3.5" />
                    {createRebuttalMut.isPending
                      ? "Creating…"
                      : selected.status === "rebutted"
                        ? "Already rebutted"
                        : "Draft a new rebuttal for this position"}
                  </Button>

                  {rebuttalTestimony.length > 0 && (
                    <div className="space-y-2 border-t border-slate-100 pt-2">
                      <div className="text-xs font-medium text-slate-700">
                        …or link an existing rebuttal/surrebuttal
                      </div>
                      {rebuttalTestimony.map((t) => (
                        <button
                          key={t.id}
                          onClick={() =>
                            linkMut.mutate({ positionId: selected.id, testimonyId: t.id })
                          }
                          disabled={linkMut.isPending || selected.status === "rebutted"}
                          className="flex w-full items-start gap-2 rounded-md border border-slate-200 bg-white p-2.5 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/40 disabled:opacity-50"
                        >
                          <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <Badge variant={t.kind === "rebuttal" ? "warning" : "violet"}>
                                {t.kind}
                              </Badge>
                              <Badge variant="outline">{t.status}</Badge>
                            </div>
                            <div className="mt-0.5 line-clamp-2 text-xs font-medium text-slate-800">
                              {t.title}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}

function NewPositionDialog({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [intervenor, setIntervenor] = useState("");
  const [intervenorKind, setIntervenorKind] = useState("staff");
  const [topic, setTopic] = useState("");
  const [positionText, setPositionText] = useState("");
  const [sourceCitation, setSourceCitation] = useState("");
  const [proposedAdjustment, setProposedAdjustment] = useState("");
  const [impactM, setImpactM] = useState<string>("");

  const createMut = useMutation({
    mutationFn: () =>
      api.createPosition({
        case_id: caseId,
        intervenor,
        intervenor_kind: intervenorKind,
        topic,
        position_text: positionText,
        source_citation: sourceCitation || null,
        proposed_adjustment: proposedAdjustment || null,
        impact_amount_m: impactM ? parseFloat(impactM) : null,
        filed_date: new Date().toISOString().slice(0, 10),
      } as any),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "positions"] });
      setOpen(false);
      setIntervenor("");
      setTopic("");
      setPositionText("");
      setSourceCitation("");
      setProposedAdjustment("");
      setImpactM("");
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-3.5 w-3.5" />
          Log position
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Log an intervenor position</DialogTitle>
          <DialogDescription>
            Captures a position taken by another party (staff, consumer advocate,
            industrial intervenor, etc.) that this utility may want to rebut.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-700">Intervenor</label>
            <Input value={intervenor} onChange={(e) => setIntervenor(e.target.value)} placeholder="CPUC-X Staff" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Kind</label>
            <Select value={intervenorKind} onValueChange={setIntervenorKind}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="staff">Staff</SelectItem>
                <SelectItem value="consumer_advocate">Consumer advocate</SelectItem>
                <SelectItem value="industrial">Industrial intervenor</SelectItem>
                <SelectItem value="environmental">Environmental intervenor</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium text-slate-700">Topic</label>
            <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Return on Equity" />
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium text-slate-700">Position text</label>
            <Textarea
              value={positionText}
              onChange={(e) => setPositionText(e.target.value)}
              className="min-h-[120px]"
              placeholder="Staff recommends a ROE of 9.25%, 85 bps below the Company's 10.10% request, based on…"
            />
          </div>
          <div className="col-span-1">
            <label className="text-xs font-medium text-slate-700">Source citation</label>
            <Input value={sourceCitation} onChange={(e) => setSourceCitation(e.target.value)} placeholder="Smith Direct, p.14" />
          </div>
          <div className="col-span-1">
            <label className="text-xs font-medium text-slate-700">Revenue impact ($M)</label>
            <Input
              type="number"
              step="0.1"
              value={impactM}
              onChange={(e) => setImpactM(e.target.value)}
              placeholder="-22.4"
            />
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium text-slate-700">Proposed adjustment</label>
            <Input
              value={proposedAdjustment}
              onChange={(e) => setProposedAdjustment(e.target.value)}
              placeholder="Reduce ROE from 10.10% to 9.25%"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            disabled={createMut.isPending || !intervenor || !topic || !positionText}
            onClick={() => createMut.mutate()}
          >
            {createMut.isPending ? "Saving…" : "Log position"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
