import { Link } from "@tanstack/react-router";
import {
  ArrowRightFromLine,
  CheckCircle2,
  Circle,
  FileSignature,
  Gavel,
  Handshake,
  Megaphone,
  Scale,
  Stamp,
} from "lucide-react";
import { cn } from "@/lib/cn";

interface Stage {
  id: string;
  num: number;
  label: string;
  to: string;
  icon: typeof Circle;
  description: string;
  triggers: string[]; // phase types that mark this stage active or done
}

const STAGES: Stage[] = [
  {
    id: "prepare",
    num: 1,
    label: "Prepare for filing",
    to: "application-workbench",
    icon: FileSignature,
    description: "Application, schedules, COS, rate design",
    triggers: ["pre_filing"],
  },
  {
    id: "engage",
    num: 2,
    label: "Engage public",
    to: "public-notice",
    icon: Megaphone,
    description: "Public notice + comments",
    triggers: ["filing"],
  },
  {
    id: "discover",
    num: 3,
    label: "Discover & analyze",
    to: "discovery",
    icon: ArrowRightFromLine,
    description: "Inbound + outbound DRs",
    triggers: ["discovery"],
  },
  {
    id: "draft",
    num: 4,
    label: "Draft & submit",
    to: "testimony",
    icon: FileSignature,
    description: "Testimony, briefs, filing",
    triggers: ["direct_testimony", "rebuttal", "surrebuttal", "post_hearing_briefs"],
  },
  {
    id: "negotiate",
    num: 5,
    label: "Negotiate & hearings",
    to: "hearing-prep",
    icon: Handshake,
    description: "Settlements + hearings",
    triggers: ["hearing"],
  },
  {
    id: "decide",
    num: 6,
    label: "Decision & comply",
    to: "order",
    icon: Stamp,
    description: "ALJ rec, order, compliance",
    triggers: ["order", "compliance"],
  },
];

interface ProcessFlowProps {
  caseId: string;
  phases?: Array<{ phase_type: string; status: string; sequence?: number }>;
  caseStatus?: string;
}

export function ProcessFlow({ caseId, phases, caseStatus }: ProcessFlowProps) {
  // Determine the current active stage by looking at in-progress / not-started phases
  const active = (() => {
    if (caseStatus === "closed") return 6;
    if (caseStatus === "pre_filing") return 1;
    if (!phases || phases.length === 0) return 1;
    const ordered = [...phases].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
    const firstActive = ordered.find((p) => p.status === "in_progress" || p.status === "not_started");
    if (!firstActive) return 6;
    for (let i = 0; i < STAGES.length; i++) {
      if (STAGES[i].triggers.includes(firstActive.phase_type)) return STAGES[i].num;
    }
    return 1;
  })();

  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-white to-brand-50/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-brand-700">End-to-end process</div>
          <div className="text-sm font-semibold text-slate-800">Regulatory case lifecycle</div>
        </div>
        <div className="text-[11px] text-muted-foreground">Currently at stage <strong className="text-brand-700">{active}</strong> of 6</div>
      </div>
      <div className="flex items-stretch gap-1.5 overflow-x-auto">
        {STAGES.map((s) => {
          const Icon = s.icon;
          const isDone = s.num < active;
          const isCurrent = s.num === active;
          return (
            <Link
              key={s.id}
              to={`/cases/${caseId}/${s.to}` as any}
              className={cn(
                "group relative flex min-w-[150px] flex-1 flex-col gap-1 rounded-lg border px-2.5 py-2 text-left transition-all",
                isDone && "border-emerald-200 bg-emerald-50/60 hover:border-emerald-400",
                isCurrent && "border-brand-500 bg-brand-50 shadow-soft hover:border-brand-600",
                !isDone && !isCurrent && "border-slate-200 bg-white hover:border-slate-300",
              )}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold",
                    isDone && "bg-emerald-600 text-white",
                    isCurrent && "bg-brand-600 text-white",
                    !isDone && !isCurrent && "bg-slate-200 text-slate-700",
                  )}
                >
                  {isDone ? <CheckCircle2 className="h-3 w-3" /> : s.num}
                </span>
                <Icon
                  className={cn(
                    "h-3.5 w-3.5",
                    isDone && "text-emerald-700",
                    isCurrent && "text-brand-700",
                    !isDone && !isCurrent && "text-slate-400",
                  )}
                />
              </div>
              <div className={cn(
                "text-[12px] font-semibold leading-tight",
                isCurrent ? "text-brand-800" : isDone ? "text-emerald-800" : "text-slate-700",
              )}>{s.label}</div>
              <div className="text-[10px] leading-tight text-muted-foreground">{s.description}</div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
