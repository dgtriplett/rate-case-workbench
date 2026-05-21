import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  ShieldAlert,
  TrendingDown,
  UserPlus,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

const STATUS_BG: Record<string, string> = {
  covered: "bg-emerald-50 ring-emerald-200 text-emerald-700",
  thin: "bg-amber-50 ring-amber-200 text-amber-700",
  uncovered: "bg-rose-50 ring-rose-200 text-rose-700",
};

const STATUS_LABEL: Record<string, string> = {
  covered: "Covered",
  thin: "Thin coverage",
  uncovered: "GAP",
};

const CRIT_BADGE: Record<string, "danger" | "warning" | "slate"> = {
  must: "danger",
  should: "warning",
  nice_to_have: "slate",
};

const CRIT_LABEL: Record<string, string> = {
  must: "Must-have",
  should: "Should-have",
  nice_to_have: "Nice-to-have",
};

export function CoverageGapPanel({ caseId }: { caseId: string }) {
  const q = useQuery({
    queryKey: ["cases", caseId, "witness-coverage"],
    queryFn: () => api.witnessCoverage(caseId),
  });

  if (q.isLoading) {
    return <Skeleton className="h-64" />;
  }
  const data = q.data;
  if (!data) return null;

  const s = data.summary;
  const gaps = data.areas.filter((a) => a.coverage_status === "uncovered");
  const thin = data.areas.filter((a) => a.coverage_status === "thin");
  const covered = data.areas.filter((a) => a.coverage_status === "covered");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-brand-600" />
          Expertise coverage & gap analysis
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Compares your witness lineup against the canonical set of rate-case expertise
          areas. Highlights gaps where active DRs or intervenor positions need a witness
          you don't have yet — with recommendations for who to retain.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* KPI row */}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <StatChip
            icon={<CheckCircle2 className="h-4 w-4 text-emerald-700" />}
            value={s.covered}
            label="Areas covered"
            bg="bg-emerald-50"
          />
          <StatChip
            icon={<TrendingDown className="h-4 w-4 text-amber-700" />}
            value={s.thin}
            label="Thin (1 witness)"
            bg="bg-amber-50"
          />
          <StatChip
            icon={<AlertTriangle className="h-4 w-4 text-rose-700" />}
            value={s.uncovered}
            label="Uncovered"
            bg="bg-rose-50"
          />
          <StatChip
            icon={<Users className="h-4 w-4 text-sky-700" />}
            value={s.open_drs_in_uncovered}
            label="Open DRs in gaps"
            bg="bg-sky-50"
          />
        </div>

        {s.must_uncovered > 0 && (
          <div className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              <strong>{s.must_uncovered}</strong>{" "}
              <strong>must-have</strong> expertise area
              {s.must_uncovered === 1 ? "" : "s"} {s.must_uncovered === 1 ? "is" : "are"}{" "}
              completely uncovered. This is a defensibility risk — engage a witness or
              consultant before the next phase.
            </span>
          </div>
        )}

        {/* Gap detail */}
        {gaps.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Coverage gaps
            </div>
            {gaps.map((a) => (
              <AreaRow key={a.key} area={a} />
            ))}
          </div>
        )}

        {thin.length > 0 && (
          <details className="rounded-md border border-slate-200 bg-slate-50/40 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-amber-700">
              Thin coverage ({thin.length}) — only one witness
            </summary>
            <div className="mt-2 space-y-2">
              {thin.map((a) => (
                <AreaRow key={a.key} area={a} />
              ))}
            </div>
          </details>
        )}

        {covered.length > 0 && (
          <details className="rounded-md border border-slate-200 bg-slate-50/40 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-emerald-700">
              Covered ({covered.length})
            </summary>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {covered.map((a) => (
                <div
                  key={a.key}
                  className="rounded-md border border-emerald-100 bg-white px-2.5 py-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-800">{a.label}</span>
                    <Badge variant={CRIT_BADGE[a.criticality]}>{CRIT_LABEL[a.criticality]}</Badge>
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {a.witnesses.map((w) => w.name).join(" · ")}
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </CardContent>
    </Card>
  );
}

function AreaRow({ area }: { area: NonNullable<ReturnType<typeof useCoverage>>["areas"][number] }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2.5 text-xs",
        area.coverage_status === "uncovered"
          ? "border-rose-200 bg-rose-50/40"
          : area.coverage_status === "thin"
            ? "border-amber-200 bg-amber-50/40"
            : "border-emerald-200 bg-emerald-50/40",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-slate-900">{area.label}</span>
          <Badge variant={CRIT_BADGE[area.criticality]}>{CRIT_LABEL[area.criticality]}</Badge>
          <span
            className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1",
              STATUS_BG[area.coverage_status],
            )}
          >
            {STATUS_LABEL[area.coverage_status]}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          {area.open_drs > 0 && (
            <span><strong>{area.open_drs}</strong> open DR{area.open_drs === 1 ? "" : "s"}</span>
          )}
          {area.positions > 0 && (
            <span><strong>{area.positions}</strong> intervenor position{area.positions === 1 ? "" : "s"}</span>
          )}
        </div>
      </div>
      {area.witnesses.length > 0 && (
        <div className="mt-1.5 text-[11px] text-slate-700">
          Covered by: {area.witnesses.map((w) => w.name).join(", ")}
        </div>
      )}
      {area.recommendation && (
        <div className="mt-2 flex items-start gap-1.5 rounded-md border border-brand-100 bg-brand-50/60 p-2 text-[11px] text-slate-700">
          <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-brand-700" />
          <div>
            <span className="font-semibold text-brand-900">Recommendation: </span>
            {area.recommendation}
          </div>
        </div>
      )}
    </div>
  );
}

function StatChip({
  icon,
  value,
  label,
  bg,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
  bg: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-2.5">
      <div className={cn("flex h-8 w-8 items-center justify-center rounded-md", bg)}>
        {icon}
      </div>
      <div>
        <div className="text-xl font-semibold tracking-tight text-slate-900">{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

// Just a type helper so AreaRow can be strongly typed without an explicit import
function useCoverage(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "witness-coverage"], queryFn: () => api.witnessCoverage(caseId) }).data!;
}
