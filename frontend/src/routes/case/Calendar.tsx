import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarClock, Download, Gavel, Inbox, ScrollText, Stamp } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { fmtDate, daysUntil } from "@/lib/format";

const KIND_ICON: Record<string, any> = {
  dr_due: Inbox,
  testimony_due: ScrollText,
  brief_due: ScrollText,
  hearing: Gavel,
  compliance_due: Stamp,
  settlement_decision: Gavel,
};

const KIND_LABEL: Record<string, string> = {
  dr_due: "DR due",
  testimony_due: "Testimony",
  brief_due: "Brief",
  hearing: "Hearing",
  compliance_due: "Compliance",
  settlement_decision: "Settlement",
};

const KIND_VARIANT: Record<string, any> = {
  dr_due: "brand",
  testimony_due: "info",
  brief_due: "violet",
  hearing: "warning",
  compliance_due: "success",
  settlement_decision: "slate",
};

export default function CaseCalendar() {
  const { caseId } = useCaseContext();
  const q = useQuery({
    queryKey: ["cases", caseId, "calendar"],
    queryFn: () => api.listCalendarEvents({ case_id: caseId }),
  });

  const events = q.data ?? [];

  // Group by month (YYYY-MM)
  const groups: Record<string, any[]> = {};
  for (const e of events) {
    const m = e.when.slice(0, 7);
    (groups[m] = groups[m] || []).push(e);
  }
  const months = Object.keys(groups).sort();

  return (
    <>
      <PageHeader
        eyebrow={<>Calendar</>}
        title="Case calendar"
        description="Every dated artifact on this case — DR deadlines, testimony / brief filings, hearings, compliance, settlement decisions — in one chronological feed."
        actions={
          <a
            href={api.calendarIcsUrl(caseId)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export ICS
          </a>
        }
      />
      <div className="space-y-4 p-6">
        {q.isLoading && <Skeleton className="h-64" />}
        {!q.isLoading && events.length === 0 && (
          <EmptyState icon={<CalendarClock className="h-4 w-4" />} title="No dated artifacts yet on this case." />
        )}
        {months.map((m) => {
          const dt = new Date(m + "-01");
          const label = dt.toLocaleString("en-US", { month: "long", year: "numeric" });
          return (
            <Card key={m}>
              <CardContent className="p-0">
                <div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {label}
                </div>
                <div className="divide-y divide-slate-100">
                  {groups[m].map((e) => {
                    const Icon = KIND_ICON[e.kind] ?? CalendarClock;
                    const d = daysUntil(e.when);
                    const overdue = d != null && d < 0 && e.status !== "filed" && e.status !== "completed" && e.status !== "accepted";
                    return (
                      <Link
                        key={e.id}
                        to={e.url}
                        className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50"
                      >
                        <div className="flex w-12 shrink-0 flex-col items-center rounded-md border border-slate-200 bg-white py-1">
                          <div className="text-[10px] uppercase text-muted-foreground">{new Date(e.when).toLocaleString("en-US", { month: "short" })}</div>
                          <div className="text-base font-bold text-slate-900">{new Date(e.when).getUTCDate()}</div>
                        </div>
                        <Icon className="h-4 w-4 shrink-0 text-brand-600" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium text-slate-800">{e.title}</span>
                            <Badge variant={KIND_VARIANT[e.kind] ?? "slate"}>{KIND_LABEL[e.kind] ?? e.kind}</Badge>
                            {overdue && <Badge variant="danger">Overdue</Badge>}
                          </div>
                          {e.detail && <div className="truncate text-[11px] text-muted-foreground">{e.detail}</div>}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}
