import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CalendarClock,
  ChevronRight,
  Clock,
  FileSignature,
  GanttChart,
  Gavel,
  Inbox,
  ScrollText,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useCaseContext } from "@/lib/case-context";
import { PhaseTimeline } from "@/components/PhaseTimeline";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { DrStatusBadge, PriorityBadge } from "@/components/StatusBadges";
import { daysUntil, fmtDate, fmtRelative } from "@/lib/format";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

export default function CaseHome() {
  const { caseId, caseData } = useCaseContext();

  const phasesQ = useQuery({
    queryKey: ["cases", caseId, "phases"],
    queryFn: () => api.listPhases(caseId),
  });
  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });
  const witnessesQ = useQuery({
    queryKey: ["cases", caseId, "witnesses"],
    queryFn: () => api.listWitnesses(caseId),
  });
  const eventsQ = useQuery({
    queryKey: ["cases", caseId, "events", "recent"],
    queryFn: () =>
      api.admin.auditEvents({ case_id: caseId, limit: 8 }),
  });

  const drs = drsQ.data ?? [];
  const openDrs = drs.filter(
    (d) => d.status !== "filed" && d.status !== "approved",
  );
  const dueSoon = openDrs
    .filter((d) => {
      const days = daysUntil(d.due_date);
      return days !== null && days <= 7;
    })
    .sort((a, b) => +new Date(a.due_date) - +new Date(b.due_date))
    .slice(0, 6);
  // Fallback: when nothing is due in 7 days (e.g. a closed case), show the
  // most recent DRs on this case so the home page isn't empty.
  const recent = [...drs]
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 6);

  // Witness load
  const witnesses = witnessesQ.data ?? [];
  const witnessLoad = witnesses
    .map((w) => ({
      witness: w,
      count: drs.filter(
        (d) =>
          d.assigned_witness_id === w.id &&
          d.status !== "filed" &&
          d.status !== "approved",
      ).length,
    }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  return (
    <>
      <PageHeader
        eyebrow={
          <>
            <span className="font-mono normal-case">
              {caseData?.docket_number}
            </span>
            <span className="mx-1.5 h-1 w-1 rounded-full bg-slate-300" />
            {caseData?.jurisdiction} · {caseData?.commission}
          </>
        }
        title={caseData?.name ?? "Case"}
        description={caseData?.description ?? caseData?.utility_name}
        actions={
          <>
            <Link to="/cases/$caseId/discovery" params={{ caseId }}>
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
                <Inbox className="h-3.5 w-3.5" />
                Discovery inbox
              </span>
            </Link>
            <Link to="/cases/$caseId/board" params={{ caseId }}>
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
                <GanttChart className="h-3.5 w-3.5" />
                Phase board
              </span>
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 p-6 lg:grid-cols-3">
        {/* KPIs */}
        <Card className="lg:col-span-3">
          <CardContent className="grid grid-cols-2 gap-4 p-4 md:grid-cols-4">
            <Stat
              icon={<Inbox className="h-4 w-4 text-brand-700" />}
              label="Open DRs"
              value={openDrs.length}
              tone="brand"
            />
            <Stat
              icon={<AlertCircle className="h-4 w-4 text-amber-700" />}
              label="Due this week"
              value={dueSoon.length}
              tone="warning"
            />
            <Stat
              icon={<UserCheck className="h-4 w-4 text-sky-700" />}
              label="Witnesses engaged"
              value={witnesses.length}
              tone="info"
            />
            <Stat
              icon={<TrendingUp className="h-4 w-4 text-emerald-700" />}
              label="Filed responses"
              value={drs.filter((d) => d.status === "filed").length}
              tone="success"
            />
          </CardContent>
        </Card>

        {/* Phase timeline */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Phase progress</CardTitle>
            <CardDescription>
              Filed{" "}
              {caseData?.filed_date
                ? fmtDate(caseData.filed_date)
                : "— not yet filed"}
              {caseData?.target_decision_date && (
                <> · target decision {fmtDate(caseData.target_decision_date)}</>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {phasesQ.isLoading && <Skeleton className="h-40" />}
            {phasesQ.data && phasesQ.data.length > 0 ? (
              <PhaseTimeline phases={phasesQ.data} />
            ) : !phasesQ.isLoading ? (
              <EmptyState
                title="No phases configured."
                description="An admin must configure the jurisdiction phase template before timeline tracking begins."
              />
            ) : null}
          </CardContent>
        </Card>

        {/* Deadlines (active cases) or final order (closed cases) */}
        {caseData?.status === "closed" ? (
          <ClosedCaseSummary caseId={caseId} />
        ) : (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-brand-600" />
                {dueSoon.length > 0 ? "Upcoming DR deadlines" : "Recent DRs on this case"}
              </CardTitle>
              <CardDescription>
                {dueSoon.length > 0
                  ? "Open discovery requests due within seven days."
                  : "Most recent data requests across all phases."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              {dueSoon.length === 0 && recent.length === 0 ? (
                <EmptyState
                  icon={<Clock className="h-4 w-4" />}
                  title="No DRs on this case yet."
                />
              ) : (
                (dueSoon.length > 0 ? dueSoon : recent).map((d) => {
                  const days = daysUntil(d.due_date);
                  const isFiled = d.status === "filed" || d.status === "approved";
                  return (
                    <Link
                      key={d.id}
                      to="/cases/$caseId/discovery/$drId"
                      params={{ caseId, drId: d.id }}
                      className="group block rounded-md border border-slate-200 bg-white px-3 py-2 hover:border-brand-300"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-muted-foreground">
                              {d.dr_number}
                            </span>
                            <PriorityBadge priority={d.priority} />
                            <DrStatusBadge status={d.status} />
                          </div>
                          <div className="mt-0.5 truncate text-sm font-medium text-slate-800 group-hover:text-brand-800">
                            {d.subject}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {d.requester} · {isFiled ? "filed" : "due"} {fmtDate(d.due_date)}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {isFiled ? (
                            <Badge variant="success">Filed</Badge>
                          ) : (
                            <Badge
                              variant={
                                days != null && days <= 1
                                  ? "danger"
                                  : days != null && days <= 3
                                    ? "warning"
                                    : "slate"
                              }
                            >
                              {days != null
                                ? `${days < 0 ? "Overdue" : `${days}d`}`
                                : "—"}
                            </Badge>
                          )}
                          <ChevronRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5" />
                        </div>
                      </div>
                    </Link>
                  );
                })
              )}
            </CardContent>
          </Card>
        )}

        {/* Witness load */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-4 w-4 text-brand-600" />
              Witness load
            </CardTitle>
            <CardDescription>Open DR assignments per witness.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {witnessLoad.length === 0 && (
              <EmptyState title="No witness assignments yet." />
            )}
            {witnessLoad.map(({ witness, count }) => (
              <div
                key={witness.id}
                className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-800">
                    {witness.name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {witness.title || "—"}
                  </div>
                </div>
                <Badge variant={count > 5 ? "warning" : "brand"}>
                  {count} open
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Recent activity */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScrollText className="h-4 w-4 text-brand-600" />
              Recent activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {eventsQ.isLoading && <Skeleton className="h-32" />}
            {eventsQ.data && eventsQ.data.length === 0 && (
              <EmptyState title="No recent activity on this case." />
            )}
            <ul className="space-y-1.5">
              {(eventsQ.data ?? []).map((ev) => (
                <li
                  key={ev.id}
                  className="flex items-start gap-2.5 rounded-md px-2 py-1.5 hover:bg-slate-50"
                >
                  <div className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-800">
                      <span className="font-medium">
                        {ev.actor_email ?? "system"}
                      </span>{" "}
                      {ev.verb.replaceAll("_", " ")}{" "}
                      <span className="text-muted-foreground">
                        {ev.target_kind}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {fmtRelative(ev.created_at)}
                    </div>
                  </div>
                  <FileSignature className="mt-1 h-3.5 w-3.5 text-slate-400" />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function ClosedCaseSummary({ caseId }: { caseId: string }) {
  const orderQ = useQuery({
    queryKey: ["cases", caseId, "order"],
    queryFn: () => api.getOrder(caseId),
  });
  const o = orderQ.data;
  return (
    <Card className="lg:col-span-2 border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-white">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gavel className="h-4 w-4 text-emerald-700" />
          Case closed — final order issued
        </CardTitle>
        <CardDescription>
          {o?.order_number ? `${o.order_number} · ` : ""}
          {o?.issued_date ? `Issued ${fmtDate(o.issued_date)}` : "Order on file"}
          {o?.compliance_filings_due && (
            <> · Compliance filings due {fmtDate(o.compliance_filings_due)}</>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-3 gap-3">
        <Stat icon={<TrendingUp className="h-4 w-4 text-emerald-700" />} label="Authorized ROE" value={o?.authorized_roe_pct ?? 0} tone="success" unit="%" />
        <Stat icon={<FileSignature className="h-4 w-4 text-emerald-700" />} label="Revenue increase" value={o?.authorized_revenue_increase_m ?? 0} tone="success" unit="$M" />
        <Stat icon={<CalendarClock className="h-4 w-4 text-emerald-700" />} label="Capex approved" value={o?.capex_approved_m ?? 0} tone="success" unit="$M" />
        {o?.summary && (
          <div className="col-span-3 rounded-md border border-emerald-200 bg-white/70 p-3 text-xs leading-relaxed text-slate-700">
            {o.summary}
          </div>
        )}
        <Link
          to="/cases/$caseId/order"
          params={{ caseId }}
          className="col-span-3 text-xs font-medium text-emerald-700 hover:underline"
        >
          View full commission order →
        </Link>
      </CardContent>
    </Card>
  );
}

function Stat({
  icon,
  label,
  value,
  tone,
  unit,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: "brand" | "warning" | "info" | "success";
  unit?: string;
}) {
  const bgs: Record<typeof tone, string> = {
    brand: "bg-brand-50",
    warning: "bg-amber-50",
    info: "bg-sky-50",
    success: "bg-emerald-50",
  };
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
      <div className={`flex h-9 w-9 items-center justify-center rounded-md ${bgs[tone]}`}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-semibold tracking-tight text-slate-900">
          {value}
          {unit && <span className="ml-0.5 text-xs font-medium text-muted-foreground">{unit}</span>}
        </div>
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
      </div>
    </div>
  );
}
