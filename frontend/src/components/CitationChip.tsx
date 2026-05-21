import { BookText, ExternalLink, Quote, Sparkles, Hash, FileText } from "lucide-react";
import { cn } from "@/lib/cn";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";
import type { CitationIn, CitationOut } from "@/lib/types";

interface CitationChipProps {
  citation: CitationIn | CitationOut;
  index?: number;
  className?: string;
  onClick?: () => void;
}

function iconFor(source_type: string) {
  switch (source_type) {
    case "document":
      return FileText;
    case "kb_chunk":
      return BookText;
    case "genie_query":
      return Sparkles;
    case "prior_response":
    case "prior_case":
      return Quote;
    default:
      return Hash;
  }
}

export function CitationChip({
  citation,
  index,
  className,
  onClick,
}: CitationChipProps) {
  const Icon = iconFor(citation.source_type);
  const label = citation.label || citation.source_id;
  const snippet = citation.snippet;
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onClick}
            className={cn(
              "inline-flex items-center gap-1 rounded border border-brand-200 bg-brand-50 px-1.5 py-0.5 text-[11px] font-medium text-brand-800 transition-colors hover:bg-brand-100",
              className,
            )}
          >
            <Icon className="h-3 w-3" />
            <span className="max-w-[180px] truncate">{label}</span>
            {typeof index === "number" && (
              <span className="ml-0.5 rounded bg-white/80 px-1 text-[9px] text-brand-800">
                {index + 1}
              </span>
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-300">
              <ExternalLink className="h-3 w-3" />
              {citation.source_type}
              {"page" in citation && citation.page != null && (
                <> · p.{citation.page}</>
              )}
            </div>
            <div className="text-xs font-medium">{label}</div>
            {snippet && (
              <p className="text-[11px] leading-snug text-slate-300 line-clamp-4">
                {snippet}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
