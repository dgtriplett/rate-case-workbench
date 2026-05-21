import { useEffect, useState } from "react";
import { FileText, Lock, X, ExternalLink, Loader2, AlertCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { DocumentOut } from "@/lib/types";

const CLASS_BADGE: Record<string, "outline" | "warning" | "violet"> = {
  public: "outline",
  confidential: "warning",
  privileged: "violet",
};

export function DocumentViewer({
  doc,
  onClose,
}: {
  doc: DocumentOut | null;
  onClose: () => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!doc) return;
    setText(null);
    setErr(null);
    setLoading(true);
    const url = api.documentContentUrl(doc.id);
    fetch(url, { credentials: "include" })
      .then(async (r) => {
        if (r.status === 403) {
          throw new Error("You do not have Unity Catalog permission to read this file.");
        }
        if (!r.ok) {
          throw new Error(`Failed to load (HTTP ${r.status}): ${(await r.text()).slice(0, 200)}`);
        }
        const ct = r.headers.get("content-type") || "";
        if (ct.startsWith("application/pdf")) {
          // PDF — leave native rendering via <iframe>
          setText("__PDF__");
          return;
        }
        setText(await r.text());
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [doc]);

  if (!doc) return null;
  const url = api.documentContentUrl(doc.id);
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="h-4 w-4 shrink-0 text-brand-600" />
              <DialogTitle className="truncate text-sm">{doc.title}</DialogTitle>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Badge variant={CLASS_BADGE[doc.classification] ?? "outline"}>
                {doc.classification === "privileged" && (
                  <Lock className="mr-1 h-3 w-3" />
                )}
                {doc.classification}
              </Badge>
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-3 w-3" />
                Open
              </a>
            </div>
          </div>
        </DialogHeader>

        <div className="border-t border-slate-100 pt-2 text-[11px] text-slate-500">
          UC path: <span className="font-mono text-[10px]">{doc.uri}</span> ·
          {" "}Permissions enforced by Unity Catalog at read time.
        </div>

        <div className="h-[60vh] overflow-y-auto rounded-md border border-slate-200 bg-slate-50/50 p-4">
          {loading && (
            <div className="flex h-full items-center justify-center text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading from UC Volume…
            </div>
          )}
          {!loading && err && (
            <div className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{err}</span>
            </div>
          )}
          {!loading && !err && text === "__PDF__" && (
            <iframe
              src={url}
              title={doc.title}
              className="h-full w-full rounded border border-slate-200 bg-white"
            />
          )}
          {!loading && !err && text && text !== "__PDF__" && (
            <pre className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-slate-800">
              {text}
            </pre>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
