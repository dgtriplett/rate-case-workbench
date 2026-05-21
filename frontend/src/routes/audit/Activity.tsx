import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity as ActivityIcon,
  ExternalLink,
  FileText,
  Filter,
  History,
  Sparkles,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDateTime, fmtRelative } from "@/lib/format";
import type { EventOut } from "@/lib/types";

const VERB_TONE: Record<string, Parameters<typeof Badge>[0]["variant"]> = {
  created: "info",
  updated: "default",
  drafted: "violet",
  submitted: "warning",
  approved: "success",
  filed: "brand",
  rejected: "danger",
  agent_run: "violet",
};

function verbVariant(verb: string) {
  return VERB_TONE[verb] ?? "default";
}

export default function ActivityAudit() {
  const { caseId } = useCaseContext();
  const [filter, setFilter] = useState("");
  const [target, setTarget] = useState("all");

  const eventsQ = useQuery({
    queryKey: ["cases", caseId, "events"],
    queryFn: () =>
      api.admin.auditEvents({ case_id: caseId, limit: 200 }),
  });

  const events = (eventsQ.data ?? []).filter((e) => {
    if (target !== "all" && e.target_kind !== target) return false;
    if (filter) {
      const f = filter.toLowerCase();
      return (
        e.verb.toLowerCase().includes(f) ||
        e.target_kind.toLowerCase().includes(f) ||
        e.actor_email?.toLowerCase().includes(f) ||
        JSON.stringify(e.payload).toLowerCase().includes(f)
      );
    }
    return true;
  });

  const targetKinds = Array.from(
    new Set((eventsQ.data ?? []).map((e) => e.target_kind)),
  );

  return (
    <>
      <PageHeader
        eyebrow={<>Audit</>}
        title="Activity & audit"
        description="Full event log for this case. Each row links to MLflow traces, version history, and source records."
      />

      <div className="space-y-3 p-6">
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-white p-2.5">
          <div className="relative flex-1 min-w-[260px]">
            <Filter className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Filter by actor, verb, or payload…"
              className="pl-9"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <Select value={target} onValueChange={setTarget}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All targets</SelectItem>
              {targetKinds.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {eventsQ.isLoading && <Skeleton className="h-80" />}
        {!eventsQ.isLoading && events.length === 0 && (
          <EmptyState
            icon={<ActivityIcon className="h-4 w-4" />}
            title="No events yet."
          />
        )}

        <ol className="relative space-y-2">
          {events.map((ev) => (
            <EventRow key={ev.id} ev={ev} />
          ))}
        </ol>
      </div>
    </>
  );
}

function EventRow({ ev }: { ev: EventOut }) {
  const isAgent = ev.verb.includes("agent");
  const traceId = (ev.payload as Record<string, unknown>)?.agent_trace_id as
    | string
    | undefined;

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
            isAgent
              ? "bg-violet-50 text-violet-700"
              : "bg-brand-50 text-brand-700"
          }`}
        >
          {isAgent ? (
            <Sparkles className="h-3.5 w-3.5" />
          ) : (
            <History className="h-3.5 w-3.5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-800">
              {ev.actor_email ?? "system"}
            </span>
            <Badge variant={verbVariant(ev.verb)}>{ev.verb}</Badge>
            <span className="text-xs text-muted-foreground">
              {ev.target_kind}
            </span>
            <span className="text-xs text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">
              {fmtDateTime(ev.created_at)} · {fmtRelative(ev.created_at)}
            </span>
          </div>
          {Object.keys(ev.payload ?? {}).length > 0 && (
            <pre className="mt-1.5 overflow-x-auto rounded bg-slate-50 p-2 text-[10px] leading-relaxed text-slate-700 font-mono">
              {JSON.stringify(ev.payload, null, 2)}
            </pre>
          )}
          {traceId && (
            <a
              href="#"
              className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-brand-700 hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              MLflow trace {traceId.slice(0, 12)}
            </a>
          )}
        </div>
        <FileText className="h-3.5 w-3.5 text-slate-300" />
      </div>
    </li>
  );
}
