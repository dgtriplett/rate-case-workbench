import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Coins,
  Search,
  User,
} from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDateTime, fmtRelative } from "@/lib/format";

export default function AdminAudit() {
  const eventsQ = useQuery({
    queryKey: ["admin", "audit", "all"],
    queryFn: () => api.admin.auditEvents({ limit: 500 }),
  });

  const events = eventsQ.data ?? [];

  // Aggregate metrics
  const stats = useMemo(() => {
    const byActor: Record<string, number> = {};
    const approved = events.filter((e) => e.verb === "approved").length;
    const total = events.length;
    const drafts = events.filter((e) => e.verb.includes("draft")).length;
    const retrievals = events.filter((e) => e.verb.includes("retrieval")).length;
    let totalCost = 0;
    for (const e of events) {
      const actor = e.actor_email ?? "system";
      byActor[actor] = (byActor[actor] ?? 0) + 1;
      const c = (e.payload as Record<string, unknown>)?.cost_usd;
      if (typeof c === "number") totalCost += c;
    }
    const topActors = Object.entries(byActor)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
    const approvalRate = drafts > 0 ? Math.round((approved / drafts) * 100) : 0;
    return { total, approved, drafts, retrievals, totalCost, topActors, approvalRate };
  }, [events]);

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Audit & analytics"
        description="System-wide activity, model spend, approval rate, and retrieval quality. Every action is captured."
      />

      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-4">
        <KpiCard
          icon={<Activity className="h-4 w-4 text-brand-700" />}
          label="Total events"
          value={stats.total}
        />
        <KpiCard
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-700" />}
          label="Response approval rate"
          value={`${stats.approvalRate}%`}
        />
        <KpiCard
          icon={<Search className="h-4 w-4 text-sky-700" />}
          label="Retrievals"
          value={stats.retrievals}
        />
        <KpiCard
          icon={<Coins className="h-4 w-4 text-amber-700" />}
          label="Model spend"
          value={`$${stats.totalCost.toFixed(2)}`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 px-6 pb-6 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <User className="h-3.5 w-3.5" />
              Top actors
            </div>
            {eventsQ.isLoading && <Skeleton className="h-32" />}
            {!eventsQ.isLoading && stats.topActors.length === 0 && (
              <EmptyState title="No activity yet." />
            )}
            <ul className="space-y-1">
              {stats.topActors.map(([actor, count]) => (
                <li
                  key={actor}
                  className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-1.5"
                >
                  <span className="text-sm font-medium text-slate-800">
                    {actor}
                  </span>
                  <Badge variant="brand">{count}</Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardContent className="p-0">
            <div className="border-b border-border bg-slate-50/60 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Recent events (system-wide)
            </div>
            <ul>
              {events.slice(0, 14).map((ev) => (
                <li
                  key={ev.id}
                  className="flex items-center justify-between border-b border-border px-4 py-2 last:border-0"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium text-slate-800">
                        {ev.actor_email ?? "system"}
                      </span>
                      <Badge variant="outline">{ev.verb}</Badge>
                      <span className="text-muted-foreground">
                        {ev.target_kind}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {fmtDateTime(ev.created_at)} · {fmtRelative(ev.created_at)}
                    </div>
                  </div>
                  <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function KpiCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-50">
          {icon}
        </div>
        <div>
          <div className="text-2xl font-semibold tracking-tight text-slate-900">
            {value}
          </div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {label}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
