import { useEffect, useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import {
  ArrowLeft,
  CheckCheck,
  ChevronRight,
  Database,
  FileText,
  History,
  Save,
  Send,
  Shield,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentChat, type ChatMessage } from "@/components/AgentChat";
import { CitationChip } from "@/components/CitationChip";
import { PositionConsistencyRail } from "@/components/PositionConsistencyRail";
import { EvidencePanel } from "@/components/EvidencePanel";
import { ChecklistPanel } from "@/components/ChecklistPanel";
import { DraftToolbar } from "@/components/DraftToolbar";
import { GenieResultCard } from "@/components/GenieResultCard";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import {
  DrStatusBadge,
  PriorityBadge,
  ResponseStatusBadge,
} from "@/components/StatusBadges";
import { fmtDate, fmtDateTime } from "@/lib/format";
import type {
  CitationIn,
  PositionWarning,
  ResponseOut,
} from "@/lib/types";

export default function Drafter() {
  const { caseId, caseData } = useCaseContext();
  const { drId } = useParams({ strict: false }) as { drId: string };
  const qc = useQueryClient();

  // -------- DR + responses --------
  const drQ = useQuery({
    queryKey: ["dr", drId],
    queryFn: () => api.getDataRequest(drId),
  });
  const currentRespQ = useQuery<ResponseOut | null>({
    queryKey: ["dr", drId, "response"],
    queryFn: () => api.getCurrentResponse(drId),
  });
  const allDrsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });
  const memoryQ = useQuery({
    queryKey: ["memory", caseId],
    queryFn: () => api.listMemory({ case_id: caseId }),
  });

  // -------- Local state --------
  const [draftText, setDraftText] = useState("");
  const [citations, setCitations] = useState<CitationIn[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [positionWarnings, setPositionWarnings] = useState<PositionWarning[]>(
    [],
  );

  // Pinned Genie results — simulated demo state; backend can hydrate later.
  const [pinnedGenie] = useState(
    [] as Array<{
      id: string;
      question: string;
      sql?: string;
      rows: Record<string, unknown>[];
      source_room?: string;
    }>,
  );

  useEffect(() => {
    if (currentRespQ.data) {
      setDraftText(
        currentRespQ.data.final_text ?? currentRespQ.data.draft_text ?? "",
      );
      setCitations(
        currentRespQ.data.citations.map((c) => ({
          source_type: c.source_type,
          source_id: c.source_id,
          label: c.label ?? undefined,
          snippet: c.snippet ?? undefined,
          page: c.page ?? undefined,
        })),
      );
    }
  }, [currentRespQ.data?.id]);

  // -------- Mutations --------
  const draftMut = useMutation({
    mutationFn: (userInstruction?: string) =>
      api.draft({
        data_request_id: drId,
        user_instruction: userInstruction,
        extra_context: draftText ? `Current draft:\n${draftText}` : undefined,
      }),
    onMutate: (userInstruction) => {
      if (userInstruction) {
        setMessages((m) => [
          ...m,
          {
            id: `u-${Date.now()}`,
            role: "user",
            content: userInstruction,
          },
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: "",
            pending: true,
          },
        ]);
      } else {
        setMessages((m) => [
          ...m,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: "",
            pending: true,
          },
        ]);
      }
    },
    onSuccess: (res) => {
      setDraftText(res.draft_text);
      setCitations(res.citations);
      setPositionWarnings(
        (res.position_warnings ?? []).map((w) => ({
          severity: "warning",
          fact_text: w,
          topic_key: "Position",
          source_label: "Agent",
        })),
      );
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant" && last.pending) {
          copy[copy.length - 1] = {
            ...last,
            pending: false,
            content: res.draft_text,
            steps: res.steps,
          };
        } else {
          copy.push({
            id: `a-${Date.now()}`,
            role: "assistant",
            content: res.draft_text,
            steps: res.steps,
          });
        }
        return copy;
      });
    },
    onError: (err) => {
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant" && last.pending) {
          copy[copy.length - 1] = {
            ...last,
            pending: false,
            content: `_Error from agent: ${(err as Error).message}_`,
          };
        }
        return copy;
      });
    },
  });

  const saveMut = useMutation({
    mutationFn: () =>
      api.saveDraft(drId, {
        draft_text: draftText,
        citations,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dr", drId, "response"] });
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
    },
  });

  const submitMut = useMutation({
    mutationFn: () => {
      if (!currentRespQ.data) throw new Error("No response to submit");
      return api.submitResponse(currentRespQ.data.id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dr", drId] });
      qc.invalidateQueries({ queryKey: ["dr", drId, "response"] });
    },
  });

  const positionCheckMut = useMutation({
    mutationFn: () => api.positionCheck(caseId, draftText),
    onSuccess: (res) => setPositionWarnings(res.warnings),
  });

  // -------- Derived data --------
  const dr = drQ.data;
  const allDrs = allDrsQ.data ?? [];
  const memories = memoryQ.data ?? [];

  const priorInThisCase = useMemo(() => {
    if (!dr) return [];
    return allDrs
      .filter(
        (x) =>
          x.id !== dr.id &&
          (x.topic_tags.some((t) => dr.topic_tags.includes(t)) ||
            x.requester === dr.requester),
      )
      .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
      .slice(0, 8);
  }, [dr, allDrs]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-50/40">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-3 border-b border-border bg-white px-5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Link
            to="/cases/$caseId/discovery"
            params={{ caseId }}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border text-slate-500 hover:bg-slate-50"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </Link>
          {drQ.isLoading ? (
            <Skeleton className="h-6 w-64" />
          ) : dr ? (
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {dr.dr_number}
                </span>
                <DrStatusBadge status={dr.status} />
                <PriorityBadge priority={dr.priority} />
                {currentRespQ.data && (
                  <ResponseStatusBadge status={currentRespQ.data.status} />
                )}
              </div>
              <div className="truncate text-base font-semibold tracking-tight text-slate-900">
                {dr.subject}
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {dr && <WorkflowStepper status={dr.status} />}
          <div className="mx-2 h-6 w-px bg-border" />
          <Button
            variant="outline"
            size="sm"
            onClick={() => positionCheckMut.mutate()}
            disabled={!draftText || positionCheckMut.isPending}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Position check
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => saveMut.mutate()}
            disabled={!draftText || saveMut.isPending}
          >
            <Save className="h-3.5 w-3.5" />
            Save draft
          </Button>
          <Button
            size="sm"
            onClick={() => submitMut.mutate()}
            disabled={!currentRespQ.data || submitMut.isPending}
          >
            <Send className="h-3.5 w-3.5" />
            Submit for review
          </Button>
        </div>
      </div>

      {/* Three-pane workspace */}
      <div className="grid h-full min-h-0 flex-1 grid-cols-12 gap-0 overflow-hidden">
        {/* LEFT pane — DR + prior DRs */}
        <aside className="col-span-3 flex h-full min-h-0 flex-col border-r border-border bg-white">
          <div className="border-b border-border px-4 py-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Data request
            </h3>
            {dr ? (
              <>
                <div className="mt-2 text-sm font-semibold text-slate-900">
                  {dr.subject}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  Issued {fmtDate(dr.issued_date)} · Due {fmtDate(dr.due_date)}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                  <Meta label="Requester" value={dr.requester} />
                  <Meta
                    label="Type"
                    value={dr.requester_kind ?? "—"}
                    capitalize
                  />
                </div>
                {dr.topic_tags.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {dr.topic_tags.map((t) => (
                      <Badge key={t} variant="outline">
                        {t}
                      </Badge>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <Skeleton className="mt-2 h-16" />
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-4 scrollbar-thin">
            <h4 className="mb-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              Request body
            </h4>
            <div className="rounded-md border border-slate-200 bg-slate-50/60 p-3 text-xs leading-relaxed text-slate-800 whitespace-pre-wrap">
              {dr?.body ?? "—"}
            </div>

            <h4 className="mb-1.5 mt-5 text-[10px] uppercase tracking-wider text-muted-foreground">
              Other DRs in this case
            </h4>
            <div className="space-y-1.5">
              {priorInThisCase.length === 0 ? (
                <div className="rounded-md border border-dashed border-slate-200 bg-white p-3 text-[11px] text-muted-foreground">
                  No related DRs in this case yet.
                </div>
              ) : (
                priorInThisCase.map((d) => (
                  <Link
                    key={d.id}
                    to="/cases/$caseId/discovery/$drId"
                    params={{ caseId, drId: d.id }}
                    className="block rounded-md border border-slate-200 bg-white p-2 hover:border-brand-300"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {d.dr_number}
                      </span>
                      <DrStatusBadge status={d.status} />
                    </div>
                    <div className="mt-1 line-clamp-2 text-[11px] font-medium text-slate-800">
                      {d.subject}
                    </div>
                  </Link>
                ))
              )}
            </div>
          </div>
        </aside>

        {/* CENTER pane — Agent chat + Draft editor */}
        <section className="col-span-6 flex h-full min-h-0 flex-col">
          <Tabs defaultValue="draft" className="flex h-full min-h-0 flex-col">
            <div className="flex items-center justify-between border-b border-border bg-white px-4 py-2">
              <TabsList>
                <TabsTrigger value="draft">
                  <FileText className="h-3.5 w-3.5" />
                  Draft
                </TabsTrigger>
                <TabsTrigger value="chat">
                  <Sparkles className="h-3.5 w-3.5" />
                  Agent
                </TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2">
                {currentRespQ.data && (
                  <span className="text-xs text-muted-foreground">
                    v{currentRespQ.data.version} ·{" "}
                    {currentRespQ.data.updated_at
                      ? fmtDateTime(currentRespQ.data.updated_at)
                      : "—"}
                  </span>
                )}
                <Button
                  size="sm"
                  onClick={() => draftMut.mutate(undefined)}
                  disabled={draftMut.isPending}
                >
                  <Wand2 className="h-3.5 w-3.5" />
                  {currentRespQ.data?.draft_text
                    ? "Regenerate with agent"
                    : "Draft with agent"}
                </Button>
              </div>
            </div>

            <TabsContent
              value="draft"
              className="flex-1 min-h-0 overflow-hidden p-0"
            >
              <div className="flex h-full flex-col">
                <div className="flex-1 min-h-0 overflow-y-auto p-5 scrollbar-thin space-y-3">
                  {currentRespQ.data?.id && (
                    <DraftToolbar
                      kind="response"
                      targetId={currentRespQ.data.id}
                      currentText={draftText}
                      onTextChange={(t) => setDraftText(t)}
                      onSaved={() =>
                        qc.invalidateQueries({
                          queryKey: ["data-requests", drId, "response"],
                        })
                      }
                    />
                  )}
                  <Textarea
                    value={draftText}
                    onChange={(e) => setDraftText(e.target.value)}
                    placeholder="Draft text will appear here. Use the agent to retrieve evidence and propose a grounded draft, then refine inline."
                    className="min-h-[420px] resize-none border-slate-200 bg-white p-5 text-[15px] leading-relaxed shadow-soft"
                  />

                  {citations.length > 0 && (
                    <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                        <Database className="h-3.5 w-3.5 text-brand-600" />
                        Citations ({citations.length})
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {citations.map((c, i) => (
                          <CitationChip
                            key={`${c.source_id}-${i}`}
                            citation={c}
                            index={i}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t border-border bg-white px-5 py-2 text-[11px] text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>
                      {draftText.length.toLocaleString()} characters · ~
                      {Math.max(1, Math.round(draftText.split(/\s+/).length))} words
                    </span>
                    {currentRespQ.data?.agent_trace_id && (
                      <a
                        className="inline-flex items-center gap-1 hover:underline"
                        href="#"
                      >
                        <Shield className="h-3 w-3" />
                        MLflow trace {currentRespQ.data.agent_trace_id.slice(0, 8)}
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent
              value="chat"
              className="flex-1 min-h-0 overflow-hidden p-0"
            >
              <AgentChat
                messages={messages}
                onSubmit={(text) => draftMut.mutate(text)}
                isPending={draftMut.isPending}
              />
            </TabsContent>
          </Tabs>
        </section>

        {/* RIGHT rail — the differentiator */}
        <aside className="col-span-3 flex h-full min-h-0 flex-col border-l border-border bg-white">
          <div className="border-b border-border px-4 py-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Grounding
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Memory, prior responses, retrieved evidence, and Genie results
              ground each draft.
            </p>
          </div>

          <Tabs
            defaultValue="position"
            className="flex h-full min-h-0 flex-col"
          >
            <div className="border-b border-border bg-white px-3 py-2">
              <TabsList className="flex w-full">
                <TabsTrigger value="position" className="flex-1">
                  Position
                  {positionWarnings.length > 0 && (
                    <Badge
                      variant={
                        positionWarnings.some((w) => w.severity === "conflict")
                          ? "danger"
                          : "warning"
                      }
                      className="ml-1 text-[9px]"
                    >
                      {positionWarnings.length}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="case" className="flex-1">
                  Case
                </TabsTrigger>
                <TabsTrigger value="jur" className="flex-1">
                  Jurisdiction
                </TabsTrigger>
                <TabsTrigger value="genie" className="flex-1">
                  Genie
                </TabsTrigger>
                <TabsTrigger value="checklist" className="flex-1">
                  Checklist
                </TabsTrigger>
                <TabsTrigger value="cites" className="flex-1">
                  Cites
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3 scrollbar-thin">
              <TabsContent value="position">
                <PositionConsistencyRail
                  warnings={positionWarnings}
                  memories={memories}
                  loading={positionCheckMut.isPending}
                />
              </TabsContent>

              <TabsContent value="case">
                <EvidencePanel
                  caseId={caseId}
                  scope="case"
                  initialQuery={dr?.subject ?? ""}
                  emptyMessage="Search this case's docs and prior responses."
                />
              </TabsContent>

              <TabsContent value="jur">
                <div className="mb-2 text-xs text-muted-foreground">
                  Searching jurisdiction:{" "}
                  <span className="font-medium text-slate-700">
                    {caseData?.jurisdiction}
                  </span>
                </div>
                <EvidencePanel
                  caseId={caseId}
                  scope="jurisdiction"
                  initialQuery={dr?.subject ?? ""}
                  emptyMessage="Search precedent across this jurisdiction."
                />
              </TabsContent>

              <TabsContent value="genie">
                <div className="space-y-2">
                  {pinnedGenie.length === 0 && (
                    <div className="rounded-md border border-dashed border-slate-200 bg-white p-3 text-[11px] text-muted-foreground">
                      No pinned Genie results yet. Ask the agent to query a
                      Genie room — pinned results appear here.
                    </div>
                  )}
                  {pinnedGenie.map((g) => (
                    <GenieResultCard key={g.id} result={g} />
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="checklist">
                <ChecklistPanel
                  kind="response"
                  text={draftText}
                  caseId={caseId}
                  onApplyAddendum={(addendum) =>
                    setDraftText(
                      (cur) => (cur.trim() ? cur + "\n\n" + addendum : addendum),
                    )
                  }
                />
              </TabsContent>

              <TabsContent value="cites">
                <div className="space-y-1.5">
                  {citations.length === 0 ? (
                    <div className="rounded-md border border-dashed border-slate-200 bg-white p-3 text-[11px] text-muted-foreground">
                      Citations attached to this draft will appear here.
                    </div>
                  ) : (
                    citations.map((c, i) => (
                      <div
                        key={`${c.source_id}-${i}`}
                        className="rounded-md border border-slate-200 bg-white p-2.5 text-xs"
                      >
                        <div className="mb-1 flex items-center justify-between">
                          <CitationChip citation={c} index={i} />
                          {c.page != null && (
                            <Badge variant="outline" className="text-[10px]">
                              p.{c.page}
                            </Badge>
                          )}
                        </div>
                        {c.snippet && (
                          <p className="text-slate-700 line-clamp-4 leading-snug">
                            {c.snippet}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </TabsContent>
            </div>
          </Tabs>

          {currentRespQ.data && (
            <div className="border-t border-border bg-slate-50/60 px-4 py-3 text-[11px]">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <History className="h-3 w-3" />
                  Version {currentRespQ.data.version}
                </span>
                <Link
                  to="/cases/$caseId/activity"
                  params={{ caseId }}
                  className="inline-flex items-center gap-0.5 text-brand-700 hover:underline"
                >
                  View history
                  <ChevronRight className="h-3 w-3" />
                </Link>
              </div>
              {currentRespQ.data.approved_at && (
                <div className="mt-1 inline-flex items-center gap-1 text-emerald-700">
                  <CheckCheck className="h-3 w-3" />
                  Approved {fmtDateTime(currentRespQ.data.approved_at)}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
  capitalize,
}: {
  label: string;
  value: string | number | null | undefined;
  capitalize?: boolean;
}) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={`text-[11px] text-slate-800 ${
          capitalize ? "capitalize" : ""
        }`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}
