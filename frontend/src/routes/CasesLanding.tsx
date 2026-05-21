import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Briefcase,
  Building2,
  Calendar,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { useState, useMemo } from "react";

import { api } from "@/lib/api";
import type { CaseOut } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/lib/auth";
import { fmtDate } from "@/lib/format";

function StatusPill({ status }: { status: CaseOut["status"] }) {
  const map: Record<string, Parameters<typeof Badge>[0]["variant"]> = {
    pre_filing: "slate",
    active: "brand",
    on_hold: "warning",
    closed: "outline",
  };
  return (
    <Badge variant={map[status]}>
      {status.replace("_", " ")}
    </Badge>
  );
}

function CaseCard({ c }: { c: CaseOut }) {
  return (
    <Link to="/cases/$caseId" params={{ caseId: c.id }} className="group block">
      <Card className="h-full transition-all hover:border-brand-300 hover:shadow-elevated">
        <CardContent className="flex h-full flex-col gap-3 p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-50 to-brand-100 text-brand-700">
                <Briefcase className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-mono text-muted-foreground">
                  {c.docket_number}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {c.jurisdiction}
                </div>
              </div>
            </div>
            <StatusPill status={c.status} />
          </div>
          <div className="flex-1">
            <h3 className="line-clamp-2 text-base font-semibold tracking-tight text-slate-900">
              {c.name}
            </h3>
            <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Building2 className="h-3.5 w-3.5" />
              {c.utility_name}
              <span className="mx-1.5 h-1 w-1 rounded-full bg-slate-300" />
              {c.commission}
            </div>
          </div>
          <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              {c.target_decision_date
                ? `Decision target ${fmtDate(c.target_decision_date)}`
                : "Decision target TBD"}
            </div>
            <span className="inline-flex items-center gap-1 font-medium text-brand-700 transition-transform group-hover:translate-x-0.5">
              Open
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function CasesLanding() {
  const { data: me } = useCurrentUser();
  const { data, isLoading } = useQuery<CaseOut[]>({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
  });
  const [filter, setFilter] = useState("");

  const cases = useMemo(() => {
    const list = data ?? [];
    const f = filter.trim().toLowerCase();
    if (!f) return list;
    return list.filter(
      (c) =>
        c.name.toLowerCase().includes(f) ||
        c.docket_number.toLowerCase().includes(f) ||
        c.jurisdiction.toLowerCase().includes(f) ||
        c.utility_name.toLowerCase().includes(f),
    );
  }, [data, filter]);

  const isAdmin = me?.roles?.includes("admin");

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div className="relative overflow-hidden border-b border-border bg-white">
        <div className="bg-grid-soft absolute inset-0 opacity-50" />
        <div className="relative px-6 py-10">
          <div className="mx-auto max-w-5xl">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-800">
              <Sparkles className="h-3 w-3" />
              Agentic regulatory operations
            </div>
            <h1 className="text-balance text-3xl font-semibold tracking-tight text-slate-900">
              Welcome
              {me?.display_name ? `, ${me.display_name.split(" ")[0]}` : ""}.
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Manage every utility rate case end-to-end. Track phases and
              deadlines, draft discovery responses with an agent that grounds
              in your case record, jurisdiction precedent, and prior positions
              — then route through review, approval, and filing.
            </p>

            <div className="mt-5 flex items-center gap-2">
              <div className="relative w-full max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by case name, docket, jurisdiction, utility…"
                  className="h-10 pl-9"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
              </div>
              {isAdmin && (
                <Link to="/admin/cases">
                  <Button>
                    <Plus className="h-4 w-4" />
                    New case
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 py-8">
        <div className="mx-auto max-w-5xl">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-tight text-slate-800">
              Active cases
            </h2>
            <span className="text-xs text-muted-foreground">
              {cases.length} case{cases.length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoading && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-44 w-full" />
              ))}
            </div>
          )}

          {!isLoading && cases.length === 0 && (
            <EmptyState
              icon={<Briefcase className="h-5 w-5" />}
              title={filter ? "No cases match your search." : "No cases yet."}
              description={
                filter
                  ? "Try a different keyword or clear the filter."
                  : "Start by creating your first case from the admin portal."
              }
              action={
                isAdmin ? (
                  <Link to="/admin/cases">
                    <Button>
                      <Plus className="h-4 w-4" />
                      Create case
                    </Button>
                  </Link>
                ) : null
              }
            />
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {cases.map((c) => (
              <CaseCard key={c.id} c={c} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
