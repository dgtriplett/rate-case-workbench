import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarRange, Flag, ScrollText } from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { KanbanColumn } from "@/components/KanbanColumn";
import { DrStatusBadge, PriorityBadge, ResponseStatusBadge } from "@/components/StatusBadges";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PHASE_LABELS, fmtDate } from "@/lib/format";
import {
  PHASE_TYPES,
  type DataRequestOut,
  type PhaseOut,
  type PhaseType,
  type TestimonyKind,
  type TestimonyOut,
} from "@/lib/types";

const TESTIMONY_PHASE: Record<TestimonyKind, PhaseType> = {
  direct: "direct_testimony",
  initial_brief: "post_hearing_briefs",
  reply_brief: "post_hearing_briefs",
  rebuttal: "rebuttal",
  surrebuttal: "surrebuttal",
};

export default function PhaseBoard() {
  const { caseId } = useCaseContext();

  const phasesQ = useQuery({
    queryKey: ["cases", caseId, "phases"],
    queryFn: () => api.listPhases(caseId),
  });
  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });
  const testimonyQ = useQuery({
    queryKey: ["cases", caseId, "testimony"],
    queryFn: () => api.listTestimony(caseId),
  });

  const phases = phasesQ.data ?? [];
  const drs = drsQ.data ?? [];
  const testimony = testimonyQ.data ?? [];

  // Build columns by phase type — even if no phase record exists for a phase type
  const columns = PHASE_TYPES.map((pt) => {
    const phase = phases.find((p) => p.phase_type === pt);
    return { phase_type: pt, phase };
  });

  function drsForPhase(phaseId?: string): DataRequestOut[] {
    if (!phaseId) return [];
    return drs.filter((d) => d.phase_id === phaseId);
  }

  function testimonyForPhase(phaseType: PhaseType): TestimonyOut[] {
    return testimony.filter(
      (t) => TESTIMONY_PHASE[t.kind] === phaseType,
    );
  }

  return (
    <>
      <PageHeader
        eyebrow={<>Phase board</>}
        title="Phase board"
        description="Drag-style kanban across the 10 standard phases. DRs are bucketed by phase. Phases without a record show as configurable lanes."
      />

      <div className="flex h-[calc(100%-7rem)] overflow-x-auto p-6 scrollbar-thin">
        <div className="flex gap-3">
          {phasesQ.isLoading && (
            <div className="flex gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-80 w-72" />
              ))}
            </div>
          )}

          {!phasesQ.isLoading &&
            columns.map(({ phase_type, phase }) => {
              const phaseDrs = drsForPhase(phase?.id);
              const phaseTestimony = testimonyForPhase(phase_type);
              const totalCount = phaseDrs.length + phaseTestimony.length;
              return (
                <KanbanColumn
                  key={phase_type}
                  title={PHASE_LABELS[phase_type]}
                  count={totalCount}
                  accent={
                    phase?.status === "in_progress"
                      ? "brand"
                      : phase?.status === "filed"
                        ? "info"
                        : "slate"
                  }
                  subtitle={
                    phase?.deadline_date
                      ? `due ${fmtDate(phase.deadline_date)}`
                      : undefined
                  }
                >
                  {phase && <PhaseInfoCard phase={phase} />}

                  {phaseTestimony.map((t) => (
                    <Link
                      key={`t-${t.id}`}
                      to="/cases/$caseId/testimony"
                      params={{ caseId }}
                      className="group rounded-md border border-violet-200 bg-violet-50/40 p-2.5 shadow-soft transition-all hover:border-violet-300 hover:shadow-elevated"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="violet">
                          <ScrollText className="mr-1 h-3 w-3" />
                          Testimony
                        </Badge>
                        <ResponseStatusBadge status={t.status} />
                      </div>
                      <div className="mt-1 line-clamp-2 text-sm font-medium text-slate-800 group-hover:text-violet-800">
                        {t.title}
                      </div>
                    </Link>
                  ))}

                  {totalCount === 0 && (
                    <div className="rounded-md border border-dashed border-slate-200 bg-white/40 p-3 text-center text-[11px] text-muted-foreground">
                      {phase_type === "discovery"
                        ? "No DRs assigned to this phase."
                        : phase_type === "direct_testimony" || phase_type === "rebuttal" || phase_type === "surrebuttal"
                          ? "No testimony in this phase yet."
                          : "Nothing in this phase yet."}
                    </div>
                  )}

                  {phaseDrs.map((d) => (
                    <Link
                      key={d.id}
                      to="/cases/$caseId/discovery/$drId"
                      params={{ caseId, drId: d.id }}
                      className="group rounded-md border border-slate-200 bg-white p-2.5 shadow-soft transition-all hover:border-brand-300 hover:shadow-elevated"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {d.dr_number}
                        </span>
                        <PriorityBadge priority={d.priority} />
                      </div>
                      <div className="mt-1 line-clamp-2 text-sm font-medium text-slate-800 group-hover:text-brand-800">
                        {d.subject}
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <DrStatusBadge status={d.status} />
                        <span className="text-[10px] text-muted-foreground">
                          due {fmtDate(d.due_date)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </KanbanColumn>
              );
            })}
        </div>
      </div>
    </>
  );
}

function PhaseInfoCard({ phase }: { phase: PhaseOut }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-2.5 text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-medium text-slate-700">
          <Flag className="h-3 w-3 text-brand-600" />
          Seq {phase.sequence}
        </div>
        <span className="text-[10px] capitalize text-muted-foreground">
          {phase.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <CalendarRange className="h-3 w-3" />
        {fmtDate(phase.start_date)} – {fmtDate(phase.end_date)}
      </div>
    </div>
  );
}
