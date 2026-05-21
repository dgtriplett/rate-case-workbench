import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  GavelIcon,
  Plus,
  Save,
  ScrollText,
  Send,
  Sparkles,
  Upload as UploadIcon,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ResponseStatusBadge } from "@/components/StatusBadges";
import { ChecklistPanel } from "@/components/ChecklistPanel";
import { DraftToolbar } from "@/components/DraftToolbar";
import { PresenceIndicator } from "@/components/PresenceIndicator";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate } from "@/lib/format";
import type { TestimonyKind, TestimonyOut } from "@/lib/types";

const KIND_LABEL: Record<TestimonyKind, string> = {
  direct: "Direct",
  rebuttal: "Rebuttal",
  surrebuttal: "Surrebuttal",
  initial_brief: "Initial brief",
  reply_brief: "Reply brief",
};

const KIND_VARIANT: Record<
  TestimonyKind,
  Parameters<typeof Badge>[0]["variant"]
> = {
  direct: "brand",
  rebuttal: "warning",
  surrebuttal: "violet",
  initial_brief: "info",
  reply_brief: "info",
};

export default function TestimonyStudio() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<TestimonyOut | null>(null);
  const [draft, setDraft] = useState("");
  const [newOpen, setNewOpen] = useState(false);

  const tListQ = useQuery({
    queryKey: ["cases", caseId, "testimony"],
    queryFn: () => api.listTestimony(caseId),
  });
  const witnessesQ = useQuery({
    queryKey: ["cases", caseId, "witnesses"],
    queryFn: () => api.listWitnesses(caseId),
  });

  function pick(t: TestimonyOut) {
    setSelected(t);
    setDraft(t.final_text ?? t.draft_text ?? "");
  }

  const saveMut = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("none selected");
      return api.updateTestimony(selected.id, {
        draft_text: draft,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
    },
  });

  const submitMut = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("none");
      // Save first so the latest text is captured, then submit
      if (draft && draft !== (selected.final_text ?? selected.draft_text ?? "")) {
        await api.updateTestimony(selected.id, { draft_text: draft });
      }
      return api.submitTestimony(selected.id);
    },
    onSuccess: (data) => {
      setSelected(data);
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
    },
  });

  const approveMut = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("none");
      return api.approveTestimony(selected.id);
    },
    onSuccess: (data) => {
      setSelected(data);
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
    },
  });

  const fileMut = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("none");
      return api.fileTestimony(selected.id);
    },
    onSuccess: (data) => {
      setSelected(data);
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
    },
  });

  const assistMut = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("none selected");
      // Use the Sparky docs endpoint as a general-purpose testimony assistant; it
      // retrieves over case + jurisdiction docs and produces a grounded section.
      const instruction =
        draft.trim().length === 0
          ? `Draft the opening section of ${selected.kind} testimony titled "${selected.title}". Use the case record. Cite sources inline.`
          : `Continue and strengthen this ${selected.kind} testimony draft, grounded in case + jurisdiction evidence. Keep my voice and structure.\n\nCURRENT DRAFT:\n${draft.slice(-3000)}`;
      const resp = await fetch("/api/v1/sparky/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: instruction,
          case_id: caseId,
          mode_hint: "docs",
          top_k: 8,
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      return (await resp.json()) as { answer: string };
    },
    onSuccess: (data) => {
      setDraft((d) => (d.trim() ? `${d}\n\n${data.answer}` : data.answer));
    },
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Testimony</>}
        title="Testimony studio"
        description="Draft direct, rebuttal, and surrebuttal testimony with agent assistance grounded in the case record and prior witness positions."
        actions={
          <Dialog open={newOpen} onOpenChange={setNewOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-3.5 w-3.5" />
                New testimony
              </Button>
            </DialogTrigger>
            <NewTestimonyDialog
              caseId={caseId}
              witnesses={witnessesQ.data ?? []}
              onClose={() => setNewOpen(false)}
            />
          </Dialog>
        }
      />

      <div className="grid h-[calc(100%-7rem)] grid-cols-12 gap-0 overflow-hidden">
        {/* List */}
        <aside className="col-span-4 flex h-full min-h-0 flex-col border-r border-border bg-white">
          <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 scrollbar-thin">
            {tListQ.isLoading && (
              <>
                <Skeleton className="h-20" />
                <Skeleton className="h-20" />
              </>
            )}
            {!tListQ.isLoading && (tListQ.data ?? []).length === 0 && (
              <EmptyState
                icon={<ScrollText className="h-4 w-4" />}
                title="No testimony yet"
                description="Use “New testimony” to start a direct, rebuttal, or surrebuttal piece."
              />
            )}
            {(tListQ.data ?? []).map((t) => (
              <button
                key={t.id}
                onClick={() => pick(t)}
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  selected?.id === t.id
                    ? "border-brand-300 bg-brand-50/40"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant={KIND_VARIANT[t.kind]}>
                    {KIND_LABEL[t.kind]}
                  </Badge>
                  <ResponseStatusBadge status={t.status} />
                </div>
                <div className="line-clamp-2 text-sm font-medium text-slate-800">
                  {t.title}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  Created {fmtDate(t.created_at)}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Editor */}
        <section className="col-span-8 flex h-full min-h-0 flex-col bg-slate-50/30">
          {!selected ? (
            <div className="flex flex-1 items-center justify-center p-6">
              <EmptyState
                icon={<BookOpen className="h-5 w-5" />}
                title="Select a testimony to edit"
                description="Pick a draft from the list — or create a new one."
              />
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-border bg-white px-5 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={KIND_VARIANT[selected.kind]}>
                      {KIND_LABEL[selected.kind]}
                    </Badge>
                    <ResponseStatusBadge status={selected.status} />
                  </div>
                  <h2 className="truncate text-base font-semibold text-slate-900">
                    {selected.title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => assistMut.mutate()}
                    disabled={assistMut.isPending}
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {assistMut.isPending ? "Drafting…" : "Agent assist"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => saveMut.mutate()}
                    disabled={saveMut.isPending}
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save
                  </Button>
                  {(selected.status === "draft") && (
                    <Button
                      size="sm"
                      onClick={() => submitMut.mutate()}
                      disabled={submitMut.isPending || !draft.trim()}
                    >
                      <Send className="h-3.5 w-3.5" />
                      {submitMut.isPending ? "Submitting…" : "Submit for review"}
                    </Button>
                  )}
                  {selected.status === "in_review" && (
                    <Button
                      size="sm"
                      onClick={() => approveMut.mutate()}
                      disabled={approveMut.isPending}
                    >
                      <GavelIcon className="h-3.5 w-3.5" />
                      {approveMut.isPending ? "Approving…" : "Approve"}
                    </Button>
                  )}
                  {selected.status === "approved" && (
                    <Button
                      size="sm"
                      onClick={() => fileMut.mutate()}
                      disabled={fileMut.isPending}
                    >
                      <UploadIcon className="h-3.5 w-3.5" />
                      {fileMut.isPending ? "Filing…" : "File with commission"}
                    </Button>
                  )}
                  {selected.status === "filed" && (
                    <Badge variant="success">
                      <CheckCircle2 className="mr-1 h-3 w-3" /> Filed
                    </Badge>
                  )}
                </div>
              </div>

              <div className="flex flex-1 min-h-0 overflow-hidden">
                <div className="flex-1 min-w-0 overflow-y-auto p-5 scrollbar-thin space-y-3">
                  <PresenceIndicator targetKind="testimony" targetId={selected.id} />
                  <DraftToolbar
                    kind="testimony"
                    targetId={selected.id}
                    currentText={draft}
                    onTextChange={(t) => setDraft(t)}
                    onSaved={() =>
                      qc.invalidateQueries({
                        queryKey: ["cases", caseId, "testimony"],
                      })
                    }
                  />
                  <Card>
                    <CardContent className="p-0">
                      <Textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        className="min-h-[600px] resize-none border-0 bg-white p-6 text-[15px] leading-relaxed shadow-none focus-visible:ring-0"
                        placeholder="Begin writing the testimony. Citations and exhibits can be added below."
                      />
                    </CardContent>
                  </Card>

                  {selected.witness_id && (
                    <div className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-white px-2.5 py-1 text-xs text-muted-foreground ring-1 ring-slate-200">
                      <Users className="h-3 w-3" />
                      Witness:{" "}
                      {witnessesQ.data?.find((w) => w.id === selected.witness_id)
                        ?.name ?? "—"}
                    </div>
                  )}
                </div>
                <aside className="w-[360px] shrink-0 overflow-y-auto border-l border-border bg-white/60 p-4">
                  <ChecklistPanel
                    kind="testimony"
                    targetId={selected.id}
                    text={draft}
                    caseId={caseId}
                    onApplyAddendum={(addendum) =>
                      setDraft((cur) => (cur.trim() ? cur + "\n\n" + addendum : addendum))
                    }
                  />
                </aside>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}

function NewTestimonyDialog({
  caseId,
  witnesses,
  onClose,
}: {
  caseId: string;
  witnesses: { id: string; name: string }[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<TestimonyKind>("direct");
  const [witnessId, setWitnessId] = useState<string | undefined>();
  const createMut = useMutation({
    mutationFn: () =>
      api.createTestimony({
        case_id: caseId,
        title,
        kind,
        witness_id: witnessId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "testimony"] });
      onClose();
    },
  });

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>New testimony</DialogTitle>
        <DialogDescription>
          Create a new direct, rebuttal, or surrebuttal piece.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div>
          <label className="text-xs font-medium text-slate-700">Title</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Direct testimony of Jane Doe on revenue requirements"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-700">Kind</label>
            <Select
              value={kind}
              onValueChange={(v) => setKind(v as TestimonyKind)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="direct">Direct testimony</SelectItem>
                <SelectItem value="rebuttal">Rebuttal testimony</SelectItem>
                <SelectItem value="surrebuttal">Surrebuttal testimony</SelectItem>
                <SelectItem value="initial_brief">Initial brief</SelectItem>
                <SelectItem value="reply_brief">Reply brief</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Witness</label>
            <Select value={witnessId} onValueChange={setWitnessId}>
              <SelectTrigger>
                <SelectValue placeholder="Select witness" />
              </SelectTrigger>
              <SelectContent>
                {witnesses.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={() => createMut.mutate()}
          disabled={!title || createMut.isPending}
        >
          Create
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
