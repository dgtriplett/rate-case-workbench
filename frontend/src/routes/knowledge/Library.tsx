import { useRef, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Search,
  Upload,
} from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ClassificationBadge } from "@/components/StatusBadges";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { fmtDate, fmtRelative } from "@/lib/format";
import { DocumentViewer } from "@/components/DocumentViewer";
import type { Classification, DocumentKind, DocumentOut } from "@/lib/types";

const DOC_KINDS: DocumentKind[] = [
  "filing",
  "exhibit",
  "order",
  "policy",
  "upload",
  "prior_case",
  "testimony",
];

export default function KnowledgeLibrary() {
  const { caseId } = useCaseContext();
  const [filter, setFilter] = useState("");
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [viewDoc, setViewDoc] = useState<DocumentOut | null>(null);

  const docsQ = useQuery({
    queryKey: ["cases", caseId, "documents"],
    queryFn: () => api.listDocuments(caseId),
  });

  const docs = (docsQ.data ?? []).filter((d) => {
    if (kindFilter !== "all" && d.kind !== kindFilter) return false;
    if (filter) {
      const f = filter.toLowerCase();
      return (
        d.title.toLowerCase().includes(f) ||
        d.summary?.toLowerCase().includes(f) ||
        d.topic_tags.some((t) => t.toLowerCase().includes(f))
      );
    }
    return true;
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Knowledge</>}
        title="Knowledge library"
        description="Documents indexed for retrieval — case filings, exhibits, orders, policy, prior case material, and uploads."
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-3.5 w-3.5" />
            Upload document
          </Button>
        }
      />

      <div className="space-y-3 p-6">
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-white p-2.5">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search documents by title, summary, or topic…"
              className="pl-9"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <Select value={kindFilter} onValueChange={setKindFilter}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All kinds</SelectItem>
              {DOC_KINDS.map((k) => (
                <SelectItem key={k} value={k}>
                  {k.replaceAll("_", " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="overflow-hidden rounded-lg border border-border bg-white">
          {docsQ.isLoading ? (
            <Skeleton className="h-64" />
          ) : docs.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-4 w-4" />}
              title="No documents yet."
              description="Upload filings, exhibits, orders, and prior case materials."
              action={
                <Button onClick={() => setUploadOpen(true)}>
                  <Upload className="h-3.5 w-3.5" />
                  Upload
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-32">Kind</TableHead>
                  <TableHead className="w-32">Classification</TableHead>
                  <TableHead className="w-24">Pages</TableHead>
                  <TableHead className="w-40">Indexing</TableHead>
                  <TableHead className="w-32">Added</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.map((d) => (
                  <TableRow
                    key={d.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => setViewDoc(d)}
                  >
                    <TableCell>
                      <div className="flex items-start gap-2">
                        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-brand-700 hover:underline">
                            {d.title}
                          </div>
                          {d.summary && (
                            <div className="line-clamp-2 text-xs text-muted-foreground">
                              {d.summary}
                            </div>
                          )}
                          {d.topic_tags.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {d.topic_tags.slice(0, 4).map((t) => (
                                <Badge key={t} variant="outline">
                                  {t}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="slate">
                        {d.kind.replaceAll("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <ClassificationBadge value={d.classification} />
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      {d.page_count ?? "—"}
                    </TableCell>
                    <TableCell>
                      {d.indexed_at ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                          <CheckCircle2 className="h-3 w-3" />
                          Indexed
                        </span>
                      ) : d.ingested_at ? (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Indexing…
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                          <Clock className="h-3 w-3" />
                          Pending
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmtDate(d.created_at)}
                      <div className="text-[10px]">
                        {fmtRelative(d.created_at)}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        caseId={caseId}
      />

      <DocumentViewer doc={viewDoc} onClose={() => setViewDoc(null)} />
    </>
  );
}

function UploadDialog({
  open,
  onClose,
  caseId,
}: {
  open: boolean;
  onClose: () => void;
  caseId: string;
}) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<DocumentKind>("upload");
  const [classification, setClassification] =
    useState<Classification>("public");
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const uploadMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      const form = new FormData();
      form.append("file", file);
      form.append("case_id", caseId);
      form.append("title", title || file.name);
      form.append("kind", kind);
      form.append("classification", classification);
      return api.uploadDocument(form);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "documents"] });
      setFile(null);
      setTitle("");
      onClose();
    },
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload document</DialogTitle>
          <DialogDescription>
            Upload a filing, exhibit, order, policy, or supporting document.
            Files are ingested and indexed automatically.
          </DialogDescription>
        </DialogHeader>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) {
              setFile(f);
              if (!title) setTitle(f.name);
            }
          }}
          onClick={() => fileInput.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
            dragOver
              ? "border-brand-400 bg-brand-50"
              : "border-slate-300 bg-slate-50/40 hover:bg-slate-50"
          }`}
        >
          <Upload className="mx-auto h-6 w-6 text-slate-400" />
          <p className="mt-1.5 text-sm font-medium text-slate-700">
            {file ? file.name : "Drop a file here, or click to choose"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            PDF, DOCX, TXT, MD — up to 50MB
          </p>
          <input
            ref={fileInput}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setFile(f);
                if (!title) setTitle(f.name);
              }
            }}
          />
        </div>

        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium text-slate-700">Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Document title"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium text-slate-700">Kind</label>
              <Select
                value={kind}
                onValueChange={(v) => setKind(v as DocumentKind)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOC_KINDS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {k.replaceAll("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">
                Classification
              </label>
              <Select
                value={classification}
                onValueChange={(v) =>
                  setClassification(v as Classification)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="public">Public</SelectItem>
                  <SelectItem value="confidential">Confidential</SelectItem>
                  <SelectItem value="privileged">Privileged</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {uploadMut.isError && (
            <div className="flex items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs text-rose-700">
              <AlertCircle className="h-3.5 w-3.5" />
              Upload failed. Try again.
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!file || uploadMut.isPending}
            onClick={() => uploadMut.mutate()}
          >
            {uploadMut.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Uploading…
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" /> Upload
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
