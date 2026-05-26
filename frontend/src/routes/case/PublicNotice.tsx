import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { fmtDate } from "@/lib/format";

export default function PublicNoticePage() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "notices"], queryFn: () => api.listPublicNotices(caseId) });
  const draftMut = useMutation({
    mutationFn: () => api.draftPublicNotice(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "notices"] }),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: any) => api.updatePublicNotice(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases", caseId, "notices"] }),
  });
  const notices = q.data ?? [];
  return (
    <>
      <PageHeader
        eyebrow={<>Public engagement</>}
        title="Public notices"
        description="Required pre-filing notification to customers, published via newspaper, web, and bill insert. AI can draft an initial notice tailored to the case."
        actions={
          <Button size="sm" onClick={() => draftMut.mutate()} disabled={draftMut.isPending}>
            <Sparkles className="h-3.5 w-3.5" /> {draftMut.isPending ? "Drafting…" : "Draft notice with AI"}
          </Button>
        }
      />
      <div className="space-y-3 p-6">
        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && notices.length === 0 && (
          <EmptyState icon={<Megaphone className="h-4 w-4" />} title="No public notices yet" description="Click 'Draft notice with AI' to generate one based on the case context." />
        )}
        {notices.map((n: any) => (
          <Card key={n.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-sm">
                <span>{n.title}</span>
                <div className="flex items-center gap-2">
                  <Badge variant={n.status === "published" ? "success" : n.status === "approved" ? "info" : "slate"}>{n.status}</Badge>
                  {n.publication_date && <span className="text-[11px] text-muted-foreground">published {fmtDate(n.publication_date)}</span>}
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="whitespace-pre-wrap text-xs text-slate-700">{n.body}</div>
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                Channels: {n.channels?.map((c: string) => <Badge key={c} variant="outline">{c}</Badge>) ?? "—"}
              </div>
              {n.status === "draft" && (
                <Button size="sm" variant="outline" onClick={() => updateMut.mutate({ id: n.id, body: { ...n, status: "approved" } })}>Approve</Button>
              )}
              {n.status === "approved" && (
                <Button size="sm" onClick={() => updateMut.mutate({ id: n.id, body: { ...n, status: "published", publication_date: new Date().toISOString().slice(0, 10) } })}>Mark published</Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
