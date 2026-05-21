import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  Briefcase,
  CalendarClock,
  ChevronRight,
  Gavel,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate } from "@/lib/format";
import { cn } from "@/lib/cn";

const STATUS_VARIANT: Record<string, any> = {
  pre_filing: "warning",
  active: "brand",
  on_hold: "slate",
  closed: "success",
};

const STATUS_LABEL: Record<string, string> = {
  pre_filing: "Pre-filing",
  active: "Active",
  on_hold: "On hold",
  closed: "Complete",
};

export default function PortfolioDashboard() {
  const q = useQuery({ queryKey: ["portfolio"], queryFn: () => api.getPortfolio() });
  if (q.isLoading) return <Skeleton className="m-6 h-96" />;
  const data = q.data;
  if (!data) return null;
  const t = data.totals || {};

  const cmpStatus = (a: any, b: any) => {
    const order = ["pre_filing", "active", "on_hold", "closed"];
    return order.indexOf(a.status) - order.indexOf(b.status);
  };
  const rows = [...(data.rows || [])].sort(cmpStatus);

  return (
    <>
      <PageHeader
        eyebrow={<>Portfolio</>}
        title="Regulatory case portfolio"
        description="Every case at a glance — open DRs, intervenor risk, rebuttal coverage, upcoming milestones. Click any row to drill into the case."
      />
      <div className="grid grid-cols-2 gap-3 p-6 md:grid-cols-5">
        <Kpi icon={<Briefcase className="h-4 w-4 text-brand-700" />} label="Active cases" value={t.active_cases ?? 0} />
        <Kpi icon={<AlertTriangle className="h-4 w-4 text-rose-700" />} label="Overdue DRs" value={t.total_overdue_drs ?? 0} bg="bg-rose-50" />
        <Kpi icon={<CalendarClock className="h-4 w-4 text-amber-700" />} label="Open DRs" value={t.total_open_drs ?? 0} bg="bg-amber-50" />
        <Kpi icon={<Gavel className="h-4 w-4 text-violet-700" />} label="Intervenor impact" value={`$${(t.total_position_impact_m ?? 0).toFixed(1)}M`} bg="bg-violet-50" />
        <Kpi icon={<TrendingUp className="h-4 w-4 text-emerald-700" />} label="Authorized (closed)" value={`$${(t.total_revenue_authorized_m ?? 0).toFixed(1)}M`} bg="bg-emerald-50" />
      </div>
      <div className="p-6 pt-0">
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">Case</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-right">Open DRs</th>
                    <th className="px-3 py-2 text-right">Overdue</th>
                    <th className="px-3 py-2 text-right">Position $M</th>
                    <th className="px-3 py-2 text-right">Rebuttal %</th>
                    <th className="px-3 py-2 text-right">Authorized $M</th>
                    <th className="px-3 py-2 text-right">Days to decision</th>
                    <th className="px-3 py-2 text-left">Next milestone</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((r: any) => (
                    <tr key={r.case_id} className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <Link to="/cases/$caseId" params={{ caseId: r.case_id }} className="block">
                          <div className="font-medium text-brand-700 hover:underline">{r.name}</div>
                          <div className="text-[11px] text-muted-foreground">{r.docket_number} · {r.jurisdiction}</div>
                        </Link>
                      </td>
                      <td className="px-3 py-2"><Badge variant={STATUS_VARIANT[r.status]}>{STATUS_LABEL[r.status] ?? r.status}</Badge></td>
                      <td className="px-3 py-2 text-right font-mono">{r.open_dr_count}</td>
                      <td className={cn("px-3 py-2 text-right font-mono", r.overdue_dr_count > 0 && "text-rose-700 font-semibold")}>{r.overdue_dr_count}</td>
                      <td className="px-3 py-2 text-right font-mono">{r.intervenor_position_impact_m ? `$${r.intervenor_position_impact_m.toFixed(1)}` : "—"}</td>
                      <td className="px-3 py-2 text-right font-mono">{r.rebuttal_coverage_pct ? `${r.rebuttal_coverage_pct.toFixed(0)}%` : "—"}</td>
                      <td className="px-3 py-2 text-right font-mono">{r.revenue_authorized_m != null ? `$${r.revenue_authorized_m.toFixed(1)}` : "—"}</td>
                      <td className={cn("px-3 py-2 text-right font-mono", r.days_to_decision != null && r.days_to_decision < 30 && "text-amber-700")}>
                        {r.days_to_decision != null ? `${r.days_to_decision}d` : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {r.next_milestone ? (
                          <>
                            <div className="font-medium text-slate-800">{r.next_milestone}</div>
                            <div className="text-[10px] text-muted-foreground">{r.next_milestone_date ? fmtDate(r.next_milestone_date) : ""}</div>
                          </>
                        ) : "—"}
                      </td>
                      <td className="px-3 py-2"><ChevronRight className="h-4 w-4 text-slate-400" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Kpi({ icon, label, value, bg = "bg-brand-50" }: any) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
      <div className={cn("flex h-9 w-9 items-center justify-center rounded-md", bg)}>{icon}</div>
      <div>
        <div className="text-xl font-semibold tracking-tight text-slate-900">{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}
