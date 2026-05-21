import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Database, RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { fmtDateTime } from "@/lib/format";

export default function AdminKnowledgeSources() {
  const qc = useQueryClient();
  const sourcesQ = useQuery({
    queryKey: ["admin", "knowledge-sources"],
    queryFn: () => api.admin.listKnowledgeSources(),
  });

  const reindex = useMutation({
    mutationFn: (id: string) => api.admin.reindexKnowledgeSource(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "knowledge-sources"] }),
  });

  const sources = sourcesQ.data ?? [];
  const byKind = {
    case: sources.filter((s) => s.kind === "case"),
    jurisdiction: sources.filter((s) => s.kind === "jurisdiction"),
    prior_responses: sources.filter((s) => s.kind === "prior_responses"),
  };

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Knowledge sources"
        description="Vector Search indices used for retrieval. Each case can have its own index plus shared jurisdiction and prior-responses indices."
      />

      <div className="space-y-4 p-6">
        {sourcesQ.isLoading && <Skeleton className="h-40" />}

        {!sourcesQ.isLoading && sources.length === 0 && (
          <EmptyState
            icon={<Database className="h-4 w-4" />}
            title="No vector indices registered."
            description="Configure Vector Search indices on the Databricks side, then register them here so the agent can use them."
          />
        )}

        {Object.entries(byKind).map(([kind, list]) =>
          list.length === 0 ? null : (
            <Card key={kind}>
              <CardContent className="p-0">
                <div className="flex items-center justify-between border-b border-border bg-slate-50/60 px-4 py-2">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-brand-600" />
                    <span className="text-sm font-semibold text-slate-800 capitalize">
                      {kind.replaceAll("_", " ")} indices
                    </span>
                  </div>
                  <Badge variant="brand">{list.length}</Badge>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Index</TableHead>
                      <TableHead className="w-48">Endpoint</TableHead>
                      <TableHead className="w-24">Chunks</TableHead>
                      <TableHead className="w-40">Last indexed</TableHead>
                      <TableHead className="w-28">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {list.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-mono text-xs">
                          {s.index_name}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {s.endpoint_name}
                        </TableCell>
                        <TableCell className="text-xs">
                          {s.chunk_count ?? "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {s.created_at ? fmtDateTime(s.created_at) : "—"}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => reindex.mutate(s.id)}
                            disabled={reindex.isPending}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                            Reindex
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ),
        )}
      </div>
    </>
  );
}
