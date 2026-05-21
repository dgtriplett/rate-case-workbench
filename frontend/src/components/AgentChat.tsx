import {
  Bot,
  ChevronDown,
  ChevronRight,
  Loader2,
  Send,
  Sparkles,
  User as UserIcon,
  Brain,
  Database,
  FileSearch,
  PenLine,
  ListChecks,
  CheckCircle2,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/cn";
import type { DraftStep, DraftStepKind } from "@/lib/types";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  steps?: DraftStep[];
  pending?: boolean;
  timestamp?: string;
}

interface AgentChatProps {
  messages: ChatMessage[];
  onSubmit: (text: string) => void;
  isPending?: boolean;
  placeholder?: string;
  className?: string;
}

const STEP_ICON: Record<DraftStepKind, typeof Brain> = {
  plan: ListChecks,
  retrieval: FileSearch,
  genie: Database,
  memory: Brain,
  tool: Sparkles,
  llm: PenLine,
  final: CheckCircle2,
};

const STEP_LABEL: Record<DraftStepKind, string> = {
  plan: "Planning",
  retrieval: "Retrieving evidence",
  genie: "Genie query",
  memory: "Recalling positions",
  tool: "Calling tool",
  llm: "Drafting",
  final: "Final response",
};

function StepRow({ step }: { step: DraftStep }) {
  const Icon = STEP_ICON[step.kind] ?? Sparkles;
  return (
    <div className="flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50/70 px-2.5 py-1.5">
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-700" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {STEP_LABEL[step.kind] ?? step.kind}
          </span>
        </div>
        <div className="text-xs font-medium text-slate-800">{step.label}</div>
        {step.detail && (
          <div className="text-[11px] text-muted-foreground line-clamp-2">
            {step.detail}
          </div>
        )}
      </div>
    </div>
  );
}

function ReasoningSteps({ steps }: { steps: DraftStep[] }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;
  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-white">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
      >
        <span className="flex items-center gap-1.5">
          <Brain className="h-3.5 w-3.5 text-brand-600" />
          <span className="font-medium">Agent reasoning</span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
            {steps.length} step{steps.length === 1 ? "" : "s"}
          </span>
        </span>
        {open ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
      </button>
      {open && (
        <div className="space-y-1 border-t border-slate-200 p-2">
          {steps.map((s, i) => (
            <StepRow step={s} key={i} />
          ))}
        </div>
      )}
    </div>
  );
}

export function AgentChat({
  messages,
  onSubmit,
  isPending,
  placeholder = "Ask the drafter to revise, ground a claim, or check a position…",
  className,
}: AgentChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, isPending]);

  function submit() {
    const v = input.trim();
    if (!v || isPending) return;
    onSubmit(v);
    setInput("");
  }

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div className="flex-1 min-h-0 space-y-3 overflow-y-auto p-4 scrollbar-thin">
        {messages.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/30 p-6 text-center">
            <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-700">
              <Sparkles className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-semibold text-slate-800">
              Draft this response with the agent
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              The agent will retrieve evidence from this case, jurisdictional
              precedent, prior responses, and Genie rooms — then propose a
              grounded draft you can edit.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex gap-2.5",
              m.role === "user" && "flex-row-reverse",
            )}
          >
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                m.role === "user"
                  ? "bg-slate-900 text-white"
                  : "bg-brand-50 text-brand-700",
              )}
            >
              {m.role === "user" ? (
                <UserIcon className="h-3.5 w-3.5" />
              ) : (
                <Bot className="h-3.5 w-3.5" />
              )}
            </div>
            <div
              className={cn(
                "flex max-w-[85%] flex-col gap-1",
                m.role === "user" && "items-end",
              )}
            >
              <div
                className={cn(
                  "rounded-lg px-3 py-2 text-sm",
                  m.role === "user"
                    ? "bg-slate-900 text-white"
                    : "bg-white border border-slate-200 text-slate-800 shadow-soft",
                )}
              >
                {m.pending ? (
                  <span className="inline-flex items-center gap-1.5 text-slate-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Working…
                  </span>
                ) : (
                  <div className="space-y-1.5 text-sm leading-relaxed [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_h1]:my-1 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:my-1 [&_h2]:text-sm [&_h2]:font-semibold [&_li]:ml-4 [&_li]:list-disc [&_p]:my-1 [&_pre]:rounded [&_pre]:bg-slate-100 [&_pre]:p-2 [&_pre]:font-mono [&_pre]:text-[11px] [&_strong]:font-semibold">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                )}
              </div>
              {m.role === "assistant" && m.steps && m.steps.length > 0 && (
                <ReasoningSteps steps={m.steps} />
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border bg-white px-3 py-2">
        <div className="flex items-end gap-2 rounded-lg border border-slate-200 bg-white p-1.5 transition-shadow focus-within:shadow-soft focus-within:ring-2 focus-within:ring-brand-200">
          <Textarea
            placeholder={placeholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                submit();
              }
            }}
            className="min-h-[42px] resize-none border-0 shadow-none focus-visible:ring-0"
            rows={2}
          />
          <Button
            size="icon"
            onClick={submit}
            disabled={!input.trim() || isPending}
            className="shrink-0"
            title="Send (⌘+Enter)"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="mt-1 px-1 text-[10px] text-muted-foreground">
          ⌘+Enter to send. Agent reasoning, retrievals, and citations are
          recorded on every draft.
        </div>
      </div>
    </div>
  );
}
