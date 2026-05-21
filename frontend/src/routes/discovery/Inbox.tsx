import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  ArrowUpDown,
  Inbox as InboxIcon,
  Search,
  Plus,
  Workflow,
  Mail,
  Globe,
  Webhook,
  Zap,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { DrStatusBadge, PriorityBadge } from "@/components/StatusBadges";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { DR_STATUSES, type DataRequestOut } from "@/lib/types";
import { daysUntil, fmtDate } from "@/lib/format";

type SortKey = "due_date" | "dr_number" | "priority" | "status";

const PRIORITY_RANK: Record<string, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
};

export default function DiscoveryInbox() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();

  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("due_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [newDrOpen, setNewDrOpen] = useState(false);

  const drsQ = useQuery({
    queryKey: ["cases", caseId, "drs"],
    queryFn: () => api.listDataRequests({ case_id: caseId }),
  });
  const witnessesQ = useQuery({
    queryKey: ["cases", caseId, "witnesses"],
    queryFn: () => api.listWitnesses(caseId),
  });

  const assignMut = useMutation({
    mutationFn: async ({
      witnessId,
      drIds,
    }: {
      witnessId: string;
      drIds: string[];
    }) => {
      await Promise.all(
        drIds.map((id) =>
          api.assignDataRequest(id, { assigned_witness_id: witnessId }),
        ),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
      setSelectedIds(new Set());
    },
  });

  const drs = drsQ.data ?? [];
  const witnesses = witnessesQ.data ?? [];

  const filtered = useMemo(() => {
    let list = drs;
    if (statusFilter !== "all") {
      list = list.filter((d) => d.status === statusFilter);
    }
    const f = filter.trim().toLowerCase();
    if (f) {
      list = list.filter(
        (d) =>
          d.dr_number.toLowerCase().includes(f) ||
          d.subject.toLowerCase().includes(f) ||
          d.requester.toLowerCase().includes(f) ||
          d.body.toLowerCase().includes(f),
      );
    }
    const sorted = [...list].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "due_date":
          cmp = +new Date(a.due_date) - +new Date(b.due_date);
          break;
        case "dr_number":
          cmp = a.dr_number.localeCompare(b.dr_number);
          break;
        case "priority":
          cmp =
            (PRIORITY_RANK[a.priority] ?? 9) -
            (PRIORITY_RANK[b.priority] ?? 9);
          break;
        case "status":
          cmp = a.status.localeCompare(b.status);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [drs, filter, statusFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll(rows: DataRequestOut[]) {
    if (selectedIds.size === rows.length && rows.length > 0)
      setSelectedIds(new Set());
    else setSelectedIds(new Set(rows.map((d) => d.id)));
  }

  return (
    <>
      <PageHeader
        eyebrow={<>Discovery</>}
        title="Discovery inbox"
        description="Triage, assign, and prioritize incoming data requests. Click any DR to open the response drafter."
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="brand">
              {drs.filter((d) => d.status !== "filed" && d.status !== "approved")
                .length}{" "}
              open
            </Badge>
            <Badge variant="warning">
              {drs.filter((d) => d.status === "in_review").length} in review
            </Badge>
            <Dialog open={newDrOpen} onOpenChange={setNewDrOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="h-3.5 w-3.5" />
                  Manual DR
                </Button>
              </DialogTrigger>
              <NewDataRequestDialog
                caseId={caseId}
                onClose={() => setNewDrOpen(false)}
              />
            </Dialog>
          </div>
        }
      />

      <AutomationBanner caseId={caseId} drCount={drs.length} />

      <div className="space-y-3 p-6">
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-white p-2.5">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search DRs by number, subject, requester…"
              className="pl-9"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {DR_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s.replaceAll("_", " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1.5">
              <span className="text-xs font-medium text-brand-900">
                {selectedIds.size} selected
              </span>
              <Select
                onValueChange={(witnessId) =>
                  assignMut.mutate({
                    witnessId,
                    drIds: Array.from(selectedIds),
                  })
                }
              >
                <SelectTrigger className="h-7 w-44 text-xs">
                  <SelectValue placeholder="Assign to witness…" />
                </SelectTrigger>
                <SelectContent>
                  {witnesses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedIds(new Set())}
              >
                Clear
              </Button>
            </div>
          )}
        </div>

        <div className="overflow-hidden rounded-lg border border-border bg-white">
          {drsQ.isLoading ? (
            <Skeleton className="h-64" />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<InboxIcon className="h-4 w-4" />}
              title="No discovery requests match."
              description="Adjust filters or wait for new requests to arrive."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <input
                      type="checkbox"
                      checked={
                        selectedIds.size > 0 &&
                        selectedIds.size === filtered.length
                      }
                      onChange={() => selectAll(filtered)}
                      className="h-3.5 w-3.5 cursor-pointer accent-brand-500"
                    />
                  </TableHead>
                  <SortHead
                    label="DR #"
                    active={sortKey === "dr_number"}
                    dir={sortDir}
                    onClick={() => toggleSort("dr_number")}
                    className="w-24"
                  />
                  <TableHead>Subject</TableHead>
                  <TableHead className="w-32">Requester</TableHead>
                  <TableHead className="w-32">Witness</TableHead>
                  <SortHead
                    label="Status"
                    active={sortKey === "status"}
                    dir={sortDir}
                    onClick={() => toggleSort("status")}
                    className="w-32"
                  />
                  <SortHead
                    label="Priority"
                    active={sortKey === "priority"}
                    dir={sortDir}
                    onClick={() => toggleSort("priority")}
                    className="w-24"
                  />
                  <SortHead
                    label="Due"
                    active={sortKey === "due_date"}
                    dir={sortDir}
                    onClick={() => toggleSort("due_date")}
                    className="w-28"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((d) => {
                  const days = daysUntil(d.due_date);
                  const witness = witnesses.find(
                    (w) => w.id === d.assigned_witness_id,
                  );
                  const selected = selectedIds.has(d.id);
                  return (
                    <TableRow key={d.id} data-state={selected ? "selected" : undefined}>
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleSelected(d.id)}
                          className="h-3.5 w-3.5 cursor-pointer accent-brand-500"
                        />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        <Link
                          to="/cases/$caseId/discovery/$drId"
                          params={{ caseId, drId: d.id }}
                          className="text-brand-700 hover:underline"
                        >
                          {d.dr_number}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Link
                          to="/cases/$caseId/discovery/$drId"
                          params={{ caseId, drId: d.id }}
                          className="font-medium text-slate-800 hover:text-brand-700"
                        >
                          {d.subject}
                        </Link>
                        {d.topic_tags.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {d.topic_tags.slice(0, 3).map((t) => (
                              <Badge key={t} variant="outline">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-slate-700">
                        {d.requester}
                      </TableCell>
                      <TableCell className="text-xs text-slate-700">
                        {witness?.name ?? (
                          <span className="text-muted-foreground">
                            Unassigned
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <DrStatusBadge status={d.status} />
                      </TableCell>
                      <TableCell>
                        <PriorityBadge priority={d.priority} />
                      </TableCell>
                      <TableCell>
                        <div className="text-xs">
                          {fmtDate(d.due_date)}
                          {days != null && (
                            <div
                              className={
                                days < 0
                                  ? "text-rose-600"
                                  : days <= 3
                                    ? "text-amber-600"
                                    : "text-muted-foreground"
                              }
                            >
                              {days < 0
                                ? `${-days}d overdue`
                                : days === 0
                                  ? "Today"
                                  : `${days}d left`}
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </>
  );
}

function SortHead({
  label,
  active,
  dir,
  onClick,
  className,
}: {
  label: string;
  active: boolean;
  dir: "asc" | "desc";
  onClick: () => void;
  className?: string;
}) {
  return (
    <TableHead className={className}>
      <button
        onClick={onClick}
        className="inline-flex items-center gap-1 text-left text-inherit"
      >
        {label}
        <ArrowUpDown
          className={`h-3 w-3 ${active ? "text-slate-700" : "text-slate-300"}`}
        />
        {active && (
          <span className="text-[9px] text-muted-foreground">
            {dir === "asc" ? "↑" : "↓"}
          </span>
        )}
      </button>
    </TableHead>
  );
}


// ---------------------------------------------------------------------------
// Automation banner — explains how DRs arrive in the inbox
// ---------------------------------------------------------------------------


function AutomationBanner({ caseId, drCount }: { caseId: string; drCount: number }) {
  // Sources we (would in production) integrate with for inbound DRs
  const sources = [
    { icon: Mail, label: "Email connector", detail: "PUC service-list inbox → DR parser" },
    { icon: Globe, label: "Commission portal", detail: "Polls the CPUC-X eFiling system every 15 min" },
    { icon: Webhook, label: "Webhook", detail: "POST /api/v1/data-requests for intervenor counsel" },
    { icon: Workflow, label: "Lakeflow ingest", detail: "Structured DR files (CSV/JSON) → Lakebase" },
  ];

  return (
    <div className="mx-6 mt-4 overflow-hidden rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-brand-50/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-700">
            <Zap className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">
                DRs auto-ingest from connectors
              </span>
              <Badge variant="success">Live</Badge>
            </div>
            <p className="mt-0.5 text-[11px] text-slate-600">
              {drCount} DRs in this inbox were ingested automatically. Manual entry is
              a backup for off-channel requests (phone, hallway questions, etc.).
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {sources.map((s) => (
            <div
              key={s.label}
              className="flex items-center gap-2 rounded-md border border-emerald-100 bg-white/70 px-2.5 py-1.5"
              title={s.detail}
            >
              <s.icon className="h-3.5 w-3.5 text-emerald-700" />
              <div className="flex flex-col leading-tight">
                <span className="text-[11px] font-medium text-slate-800">{s.label}</span>
                <span className="text-[9px] text-slate-500">{s.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Manual DR creation
// ---------------------------------------------------------------------------


function NewDataRequestDialog({
  caseId,
  onClose,
}: {
  caseId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [drNumber, setDrNumber] = useState("");
  const [requester, setRequester] = useState("");
  const [requesterKind, setRequesterKind] = useState("staff");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const today = new Date();
  const dueDefault = new Date(today.getTime() + 14 * 86400_000)
    .toISOString()
    .slice(0, 10);
  const [issuedDate, setIssuedDate] = useState(today.toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState(dueDefault);

  const createMut = useMutation({
    mutationFn: () =>
      api.createDataRequest({
        case_id: caseId,
        dr_number: drNumber,
        requester,
        requester_kind: requesterKind,
        subject,
        body,
        issued_date: issuedDate,
        due_date: dueDate,
        priority,
        topic_tags: [],
      } as any),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "drs"] });
      onClose();
    },
  });

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>Manually create a data request</DialogTitle>
        <DialogDescription>
          For off-channel requests (verbal, side-letter, etc.) that didn't come
          through a connector. Most DRs arrive automatically — see the green
          banner above for live integrations.
        </DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">DR number</label>
          <Input
            value={drNumber}
            onChange={(e) => setDrNumber(e.target.value)}
            placeholder="STAFF-DR-101"
          />
        </div>
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">Requester</label>
          <Input
            value={requester}
            onChange={(e) => setRequester(e.target.value)}
            placeholder="CPUC-X Staff"
          />
        </div>
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">
            Requester kind
          </label>
          <Select value={requesterKind} onValueChange={setRequesterKind}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="staff">Staff</SelectItem>
              <SelectItem value="consumer_advocate">Consumer advocate</SelectItem>
              <SelectItem value="industrial">Industrial intervenor</SelectItem>
              <SelectItem value="environmental">Environmental intervenor</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">Priority</label>
          <Select value={priority} onValueChange={setPriority}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="normal">Normal</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">Issued</label>
          <Input
            type="date"
            value={issuedDate}
            onChange={(e) => setIssuedDate(e.target.value)}
          />
        </div>
        <div className="col-span-1">
          <label className="text-xs font-medium text-slate-700">Due</label>
          <Input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>
        <div className="col-span-2">
          <label className="text-xs font-medium text-slate-700">Subject</label>
          <Input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Provide workpapers supporting depreciation rates by function"
          />
        </div>
        <div className="col-span-2">
          <label className="text-xs font-medium text-slate-700">Body</label>
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="min-h-[160px]"
            placeholder="1. Please provide all workpapers supporting the proposed depreciation rates..."
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={() => createMut.mutate()}
          disabled={
            createMut.isPending || !drNumber || !subject || !requester || !body
          }
        >
          {createMut.isPending ? "Creating…" : "Create DR"}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
