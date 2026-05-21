import { useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Plus,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { CoverageGapPanel } from "@/components/CoverageGapPanel";

export default function WitnessCoordination() {
  const { caseId } = useCaseContext();

  const witnessesQ = useQuery({
    queryKey: ["cases", caseId, "witnesses"],
    queryFn: () => api.listWitnesses(caseId),
  });
  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });

  const witnesses = witnessesQ.data ?? [];
  const drs = drsQ.data ?? [];

  // Build expertise matrix: rows = witnesses, columns = unique topic tags
  const topics = useMemo(() => {
    const s = new Set<string>();
    witnesses.forEach((w) => w.expertise_areas.forEach((e) => s.add(e)));
    drs.forEach((d) => d.topic_tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [witnesses, drs]);

  const loadByWitness = useMemo(() => {
    const map: Record<
      string,
      { open: number; total: number; topics: Set<string> }
    > = {};
    drs.forEach((d) => {
      if (!d.assigned_witness_id) return;
      if (!map[d.assigned_witness_id])
        map[d.assigned_witness_id] = {
          open: 0,
          total: 0,
          topics: new Set(),
        };
      const m = map[d.assigned_witness_id];
      m.total += 1;
      if (d.status !== "filed" && d.status !== "approved") m.open += 1;
      d.topic_tags.forEach((t) => m.topics.add(t));
    });
    return map;
  }, [drs]);

  return (
    <>
      <PageHeader
        eyebrow={<>Witnesses</>}
        title="Witness coordination"
        description="Assignment matrix, expertise coverage, and current workload across the case."
        actions={
          <NewWitnessDialog>
            <Button>
              <Plus className="h-3.5 w-3.5" />
              Add witness
            </Button>
          </NewWitnessDialog>
        }
      />

      <div className="space-y-5 p-6">
        {witnessesQ.isLoading && <Skeleton className="h-40" />}

        {!witnessesQ.isLoading && witnesses.length === 0 && (
          <EmptyState
            icon={<Users className="h-4 w-4" />}
            title="No witnesses yet"
            description="Register witnesses for this case to begin assigning DRs and testimony."
          />
        )}

        {/* Expertise / coverage gap analysis — proactive identification of holes */}
        {witnesses.length > 0 && <CoverageGapPanel caseId={caseId} />}

        {/* Roster */}
        {witnesses.length > 0 && (
          <Card>
            <CardContent className="p-0">
              <div className="grid grid-cols-1 divide-y divide-slate-200 md:grid-cols-2 md:divide-x md:divide-y-0 lg:grid-cols-3">
                {witnesses.map((w) => {
                  const load = loadByWitness[w.id] ?? {
                    open: 0,
                    total: 0,
                    topics: new Set<string>(),
                  };
                  return (
                    <div key={w.id} className="flex flex-col gap-2 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-700">
                            <Users className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-slate-900">
                              {w.name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {w.title ?? "—"}
                            </div>
                          </div>
                        </div>
                        {w.is_external && (
                          <Badge variant="violet">External</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <Metric label="Open DRs" value={load.open} tone={load.open > 5 ? "warn" : "default"} />
                        <Metric label="Total DRs" value={load.total} />
                      </div>
                      <div>
                        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                          Expertise
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {w.expertise_areas.length === 0 && (
                            <span className="text-[11px] italic text-muted-foreground">
                              No expertise tagged
                            </span>
                          )}
                          {w.expertise_areas.map((e) => (
                            <Badge key={e} variant="brand">
                              {e}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Expertise matrix */}
        {witnesses.length > 0 && topics.length > 0 && (
          <Card>
            <CardContent className="p-0">
              <div className="border-b border-border bg-slate-50/60 px-4 py-2">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Expertise / coverage matrix
                </div>
                <div className="text-[11px] text-muted-foreground">
                  ● = witness expertise · ○ = appears in assigned DR topics
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50/40">
                    <tr>
                      <th className="sticky left-0 z-10 bg-slate-50/80 px-3 py-2 text-left font-medium text-muted-foreground">
                        Witness
                      </th>
                      {topics.map((t) => (
                        <th
                          key={t}
                          className="px-2 py-2 text-center font-medium text-muted-foreground"
                          style={{ writingMode: "vertical-rl" }}
                        >
                          <span className="inline-block whitespace-nowrap text-[10px] uppercase tracking-wider">
                            {t}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {witnesses.map((w) => {
                      const load = loadByWitness[w.id] ?? {
                        topics: new Set<string>(),
                      };
                      const exp = new Set(w.expertise_areas);
                      return (
                        <tr key={w.id} className="border-t border-slate-200">
                          <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium text-slate-800">
                            {w.name}
                          </td>
                          {topics.map((t) => {
                            const expert = exp.has(t);
                            const assigned = load.topics.has(t);
                            return (
                              <td
                                key={t}
                                className="px-2 py-2 text-center"
                                title={
                                  expert
                                    ? "Expertise"
                                    : assigned
                                      ? "Assigned (no expertise)"
                                      : ""
                                }
                              >
                                {expert ? (
                                  <span className="text-brand-600">●</span>
                                ) : assigned ? (
                                  <span className="text-amber-500">○</span>
                                ) : (
                                  <span className="text-slate-200">·</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-slate-200 bg-slate-50/40 px-4 py-2 text-[11px] text-muted-foreground">
                <span className="inline-flex items-center gap-1 text-amber-600">
                  <AlertTriangle className="h-3 w-3" /> Witness assigned a DR
                  topic outside their listed expertise.
                </span>
                <span className="mx-2 text-slate-300">|</span>
                <span className="inline-flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 className="h-3 w-3" /> Topic is covered by at
                  least one expert witness.
                </span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "default" | "warn";
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={`text-base font-semibold ${
          tone === "warn" ? "text-amber-700" : "text-slate-900"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function NewWitnessDialog({ children }: { children: React.ReactNode }) {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [expertise, setExpertise] = useState("");
  const [external, setExternal] = useState(false);

  const createMut = useMutation({
    mutationFn: () =>
      api.createWitness({
        name,
        title: title || undefined,
        expertise_areas: expertise
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        is_external: external,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "witnesses"] });
      setName("");
      setTitle("");
      setExpertise("");
      setExternal(false);
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add witness</DialogTitle>
          <DialogDescription>
            Register a witness for this case.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium">
              Expertise areas (comma-separated)
            </label>
            <Input
              placeholder="rate design, depreciation, cost of capital"
              value={expertise}
              onChange={(e) => setExpertise(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={external}
              onChange={(e) => setExternal(e.target.checked)}
              className="h-3.5 w-3.5 accent-brand-500"
            />
            External witness (consultant/expert)
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => createMut.mutate()}
            disabled={!name || createMut.isPending}
          >
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
