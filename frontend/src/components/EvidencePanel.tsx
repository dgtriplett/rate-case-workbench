import { ExternalLink, FileText, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SearchHit } from "@/lib/types";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { EmptyState } from "./ui/empty";

interface EvidencePanelProps {
  caseId: string;
  initialQuery?: string;
  scope: "case" | "jurisdiction" | "both";
  emptyMessage?: string;
}

export function EvidencePanel({
  caseId,
  initialQuery = "",
  scope,
  emptyMessage = "Run a search to find supporting evidence.",
}: EvidencePanelProps) {
  const [q, setQ] = useState(initialQuery);
  const [results, setResults] = useState<SearchHit[]>([]);

  const search = useMutation({
    mutationFn: () =>
      api.knowledgeSearch({
        query: q,
        case_id: caseId,
        scope,
        top_k: 8,
      }),
    onSuccess: (data) => setResults(data),
  });

  useEffect(() => {
    if (initialQuery) {
      setQ(initialQuery);
      // auto-fire search
      api
        .knowledgeSearch({
          query: initialQuery,
          case_id: caseId,
          scope,
          top_k: 8,
        })
        .then(setResults)
        .catch(() => setResults([]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, caseId, scope]);

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={`Search ${scope === "both" ? "all sources" : scope}…`}
            className="pl-8"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") search.mutate();
            }}
          />
        </div>
        <Button
          size="sm"
          onClick={() => search.mutate()}
          disabled={!q.trim() || search.isPending}
        >
          {search.isPending ? "Searching…" : "Search"}
        </Button>
      </div>

      <div className="space-y-2">
        {results.length === 0 && !search.isPending && (
          <EmptyState
            icon={<FileText className="h-4 w-4" />}
            title="No results yet"
            description={emptyMessage}
          />
        )}
        {results.map((hit, i) => (
          <div
            key={`${hit.document_id}-${i}`}
            className="rounded-md border border-slate-200 bg-white p-2.5 text-xs"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 font-medium text-slate-800">
                <FileText className="h-3.5 w-3.5 text-brand-600" />
                <span className="truncate">{hit.document_title}</span>
              </div>
              <div className="flex items-center gap-1">
                {hit.page != null && (
                  <Badge variant="outline" className="text-[10px]">
                    p.{hit.page}
                  </Badge>
                )}
                <Badge variant="brand" className="text-[10px]">
                  {(hit.score * 100).toFixed(0)}%
                </Badge>
              </div>
            </div>
            <p className="text-slate-700 line-clamp-4 leading-snug">
              {hit.chunk_text}
            </p>
            <button className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-medium text-brand-700 hover:underline">
              Open document <ExternalLink className="h-2.5 w-2.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
