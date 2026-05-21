import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Download,
  Upload,
  Sparkles,
  Wand2,
  Loader2,
  FileText,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";

type Kind = "testimony" | "response";

export function DraftToolbar({
  kind,
  targetId,
  currentText,
  onTextChange,
  onSaved,
}: {
  kind: Kind;
  targetId: string;
  currentText: string;
  onTextChange: (text: string) => void;
  onSaved?: () => void;
}) {
  const [revisePrompt, setRevisePrompt] = useState("");
  const [reviseOpen, setReviseOpen] = useState(false);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [lastSummary, setLastSummary] = useState<string | null>(null);
  const uploadInput = useRef<HTMLInputElement>(null);

  const reviseMut = useMutation({
    mutationFn: () =>
      api.reviseDraft(kind, targetId, { instruction: revisePrompt }),
    onSuccess: (data) => {
      onTextChange(data.new_text);
      setLastSummary(data.summary);
      setRevisePrompt("");
      setReviseOpen(false);
      onSaved?.();
    },
  });

  const autoFixMut = useMutation({
    mutationFn: () => api.autoFixDraft(kind, targetId),
    onSuccess: (data) => {
      onTextChange(data.new_text);
      setLastSummary(
        data.applied_items.length === 0
          ? "Nothing to auto-fix — all checklist items pass."
          : `Applied ${data.applied_items.length} fix${data.applied_items.length === 1 ? "" : "es"}: ${data.applied_items.map((a) => a.title).join("; ")}`,
      );
      onSaved?.();
    },
  });

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(api.draftUploadUrl(kind, targetId), {
        method: "POST",
        body: form,
        credentials: "same-origin",
      });
      if (!r.ok) throw new Error(await r.text());
      // Re-fetch the now-updated draft text
      const updated =
        kind === "testimony"
          ? await api.getTestimony(targetId)
          : await api.getResponse(targetId);
      const newText =
        (updated as any).final_text || (updated as any).draft_text || "";
      onTextChange(newText);
      onSaved?.();
      return newText;
    },
  });

  function pickFile() {
    uploadInput.current?.click();
  }
  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadMut.mutate(file);
    e.target.value = "";
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/60 px-2.5 py-1.5">
      <div className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        <FileText className="h-3 w-3" /> Iterate
      </div>

      <Popover open={reviseOpen} onOpenChange={setReviseOpen}>
        <PopoverTrigger asChild>
          <Button size="sm" variant="outline" className="h-7">
            <Sparkles className="h-3 w-3" />
            Revise with AI
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[420px]" align="start">
          <div className="space-y-2">
            <div className="text-xs font-medium text-slate-700">
              Tell the AI how to revise the draft
            </div>
            <Textarea
              value={revisePrompt}
              onChange={(e) => setRevisePrompt(e.target.value)}
              className="min-h-[110px] text-[13px]"
              placeholder={
                kind === "testimony"
                  ? "e.g. Tighten the policy section, add a paragraph addressing OCA's 9.25% ROE position, cite Exhibit S-3."
                  : "e.g. Make the response more concise, add a citation to WP-2-7, and remove the speculative paragraph."
              }
            />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">
                The current draft is replaced with the AI's revision. Old text is in the audit log.
              </span>
              <Button
                size="sm"
                onClick={() => reviseMut.mutate()}
                disabled={reviseMut.isPending || !revisePrompt.trim()}
              >
                {reviseMut.isPending ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" /> Revising…
                  </>
                ) : (
                  "Apply revision"
                )}
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>

      <Button
        size="sm"
        variant="outline"
        className="h-7"
        onClick={() => autoFixMut.mutate()}
        disabled={autoFixMut.isPending || !currentText.trim()}
      >
        {autoFixMut.isPending ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" /> Auto-fixing…
          </>
        ) : (
          <>
            <Wand2 className="h-3 w-3" /> Auto-apply checklist
          </>
        )}
      </Button>

      <div className="ml-auto flex items-center gap-1">
        <Popover open={downloadOpen} onOpenChange={setDownloadOpen}>
          <PopoverTrigger asChild>
            <Button size="sm" variant="outline" className="h-7">
              <Download className="h-3 w-3" />
              Download
              <ChevronDown className="h-3 w-3" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-44 p-1" align="end">
            {(["docx", "md", "txt"] as const).map((fmt) => (
              <a
                key={fmt}
                href={api.draftDownloadUrl(kind, targetId, fmt)}
                target="_blank"
                rel="noreferrer"
                onClick={() => setDownloadOpen(false)}
                className="block rounded-md px-2.5 py-1.5 text-xs hover:bg-slate-100"
              >
                {fmt === "docx" ? "Word document (.docx)" : fmt === "md" ? "Markdown (.md)" : "Plain text (.txt)"}
              </a>
            ))}
          </PopoverContent>
        </Popover>

        <Button
          size="sm"
          variant="outline"
          className="h-7"
          onClick={pickFile}
          disabled={uploadMut.isPending}
        >
          {uploadMut.isPending ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" /> Importing…
            </>
          ) : (
            <>
              <Upload className="h-3 w-3" /> Upload revision
            </>
          )}
        </Button>
        <input
          ref={uploadInput}
          type="file"
          accept=".docx,.md,.txt,.markdown"
          className="hidden"
          onChange={handleFile}
        />
      </div>

      {lastSummary && (
        <div className="basis-full rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-900">
          <strong className="mr-1">AI:</strong> {lastSummary}
        </div>
      )}

      {(reviseMut.isError || autoFixMut.isError || uploadMut.isError) && (
        <div className="basis-full rounded-md border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] text-rose-800">
          Something went wrong — check console for details.
        </div>
      )}
    </div>
  );
}
