import { useEffect, useRef, useState } from "react";
import { Sparkles, X, Send, Loader2, BookOpen, HelpCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { useOptionalCaseContext } from "@/lib/case-context";

type SparkyCitation = {
  document_id: string;
  document_title: string;
  snippet: string;
  page?: number | null;
  source?: string;
};

type Turn = {
  role: "user" | "assistant";
  content: string;
  mode?: "docs" | "app";
  citations?: SparkyCitation[];
  pending?: boolean;
};

const STARTERS: { label: string; question: string; mode?: "docs" | "app" }[] = [
  { label: "How do I draft a response?", question: "How do I draft a response to a data request?", mode: "app" },
  { label: "What does the position-consistency rail do?", question: "What does the position-consistency rail do?", mode: "app" },
  { label: "What does the case docket cover?", question: "Summarize what this case is about based on the application", mode: "docs" },
  { label: "What ROE is requested?", question: "What ROE is the utility requesting, and on what capital structure?", mode: "docs" },
];

export function Sparky() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([
    {
      role: "assistant",
      content:
        "Hi, I'm Sparky ✨\n\nI can help two ways:\n• **App questions** — ask me how to use the workbench.\n• **Case questions** — I'll search the case + jurisdiction docs and answer with citations.\n\nWhat would you like to know?",
      mode: "app",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const caseCtx = useOptionalCaseContext();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, open]);

  async function send(text: string, hint?: "docs" | "app") {
    if (!text.trim() || busy) return;
    const next: Turn[] = [
      ...turns,
      { role: "user", content: text },
      { role: "assistant", content: "", pending: true },
    ];
    setTurns(next);
    setDraft("");
    setBusy(true);

    try {
      const resp = await fetch("/api/v1/sparky/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          case_id: caseCtx?.caseId ?? null,
          history: turns.filter((t) => !t.pending).map((t) => ({ role: t.role, content: t.content })),
          mode_hint: hint ?? null,
          top_k: 6,
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setTurns((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: data.answer,
          mode: data.mode,
          citations: data.citations,
        };
        return copy;
      });
    } catch (e: any) {
      setTurns((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: `Sorry — Sparky hit a snag: ${e?.message ?? "unknown error"}`,
        };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          aria-label="Open Sparky"
          onClick={() => setOpen(true)}
          className={cn(
            "fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full",
            "bg-gradient-to-br from-brand-500 to-emerald-600 text-white px-4 py-3",
            "shadow-elevated hover:shadow-2xl transition-all hover:-translate-y-0.5"
          )}
        >
          <Sparkles className="h-5 w-5" />
          <span className="text-sm font-medium">Ask Sparky</span>
        </button>
      )}

      {open && (
        <div
          className={cn(
            "fixed bottom-5 right-5 z-50 flex h-[600px] w-[420px] flex-col overflow-hidden",
            "rounded-2xl border border-slate-200 bg-white shadow-elevated"
          )}
        >
          <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-gradient-to-br from-brand-500/95 to-emerald-600 px-4 py-3 text-white">
            <div className="flex items-center gap-2">
              <div className="rounded-full bg-white/20 p-1.5">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold">Sparky</div>
                <div className="text-[11px] opacity-80">Rate Case Workbench assistant</div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full p-1 hover:bg-white/10 transition-colors"
              aria-label="Close Sparky"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {turns.map((t, i) => (
              <Bubble key={i} turn={t} />
            ))}
            {turns.length <= 1 && (
              <div className="space-y-2 pt-2">
                <div className="text-[11px] uppercase tracking-wide text-slate-500">Try asking</div>
                {STARTERS.map((s) => (
                  <button
                    key={s.label}
                    className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2 text-left text-xs text-slate-700 hover:border-brand-300 hover:bg-brand-50/50"
                    onClick={() => send(s.question, s.mode)}
                  >
                    {s.mode === "docs" ? (
                      <BookOpen className="h-3.5 w-3.5 text-brand-600" />
                    ) : (
                      <HelpCircle className="h-3.5 w-3.5 text-brand-600" />
                    )}
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 p-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(draft);
              }}
              className="flex items-end gap-2"
            >
              <textarea
                rows={1}
                value={draft}
                disabled={busy}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(draft);
                  }
                }}
                placeholder="Ask Sparky anything…"
                className="flex-1 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
              <button
                type="submit"
                disabled={busy || !draft.trim()}
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500 text-white shadow-sm hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
            <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
              <span>{caseCtx?.caseId ? "Scoped to current case" : "No case selected — app-help mode"}</span>
              <span className="font-medium text-slate-500">⌘+/ to toggle</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm shadow-soft",
          isUser
            ? "bg-brand-500 text-white"
            : "bg-slate-100 text-slate-800 border border-slate-200"
        )}
      >
        {turn.pending ? (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Sparky is thinking…</span>
          </div>
        ) : (
          <>
            <div className="whitespace-pre-wrap leading-relaxed">{renderMarkdownInline(turn.content)}</div>
            {turn.mode === "docs" && turn.citations && turn.citations.length > 0 && (
              <div className="mt-2 space-y-1 border-t border-slate-200/60 pt-2 text-[11px] text-slate-600">
                <div className="font-semibold text-slate-500">Sources</div>
                {turn.citations.slice(0, 5).map((c, i) => (
                  <div key={i} className="truncate">
                    [{i + 1}] {c.document_title}
                    {c.page ? `, p.${c.page}` : ""}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function renderMarkdownInline(s: string) {
  // very small bold + bullet renderer — keep deps minimal
  const out: (string | JSX.Element)[] = [];
  const lines = s.split("\n");
  lines.forEach((line, idx) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((p, j) =>
      p.startsWith("**") && p.endsWith("**") ? (
        <strong key={`${idx}-${j}`}>{p.slice(2, -2)}</strong>
      ) : (
        <span key={`${idx}-${j}`}>{p}</span>
      )
    );
    out.push(
      <span key={idx}>
        {rendered}
        {idx < lines.length - 1 ? <br /> : null}
      </span>
    );
  });
  return out;
}
