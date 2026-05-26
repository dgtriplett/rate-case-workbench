import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Smile, Frown, Meh, Mail, Globe, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate, fmtRelative } from "@/lib/format";

const SENTIMENT_VARIANT: Record<string, any> = {
  positive: "success", negative: "danger", neutral: "slate", mixed: "warning",
};
const SENTIMENT_ICON: Record<string, any> = {
  positive: Smile, negative: Frown, neutral: Meh, mixed: Meh,
};
const SOURCE_ICON: Record<string, any> = {
  email: Mail, portal: Globe, letter: FileText, oral: MessageCircle,
};

export default function PublicComments() {
  const { caseId } = useCaseContext();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cases", caseId, "comments"], queryFn: () => api.listPublicComments(caseId) });
  const summaryQ = useQuery({ queryKey: ["cases", caseId, "comments-summary"], queryFn: () => api.publicCommentsSummary(caseId) });

  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [source, setSource] = useState("email");
  const [body, setBody] = useState("");
  const createMut = useMutation({
    mutationFn: () => api.createPublicComment({
      case_id: caseId, source, commenter_name: name || null, commenter_org: org || null, body,
      received_date: new Date().toISOString().slice(0, 10),
    }),
    onSuccess: () => { setName(""); setOrg(""); setBody(""); qc.invalidateQueries({ queryKey: ["cases", caseId, "comments"] }); qc.invalidateQueries({ queryKey: ["cases", caseId, "comments-summary"] }); },
  });

  const comments = q.data ?? [];
  const summary = summaryQ.data;

  return (
    <>
      <PageHeader
        eyebrow={<>Public engagement</>}
        title="Public comments"
        description="Comments collected from email, the commission portal, written submissions, and oral testimony at public hearings. Each one is auto-classified for sentiment + topic by Claude."
      />
      <div className="p-6 space-y-4">
        {summary && (
          <Card>
            <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3 p-3">
              <Stat label="Total" value={summary.total} />
              <Stat label="Positive" value={summary.by_sentiment?.positive ?? 0} variant="success" />
              <Stat label="Negative" value={summary.by_sentiment?.negative ?? 0} variant="danger" />
              <Stat label="Mixed" value={summary.by_sentiment?.mixed ?? 0} variant="warning" />
              <div>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Top topics</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {summary.top_topics?.slice(0, 5).map((t: any) => (
                    <Badge key={t.topic} variant="outline">{t.topic} · {t.count}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader><CardTitle className="text-sm">Log a new public comment</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Commenter name" />
              <Input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="Organization (optional)" />
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="portal">Portal</SelectItem>
                  <SelectItem value="letter">Letter</SelectItem>
                  <SelectItem value="oral">Oral (hearing)</SelectItem>
                </SelectContent>
              </Select>
              <Button disabled={!body || createMut.isPending} onClick={() => createMut.mutate()}>Log comment</Button>
            </div>
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[100px]" placeholder="Paste or type the comment text — sentiment + topics auto-classified by AI on save." />
          </CardContent>
        </Card>

        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && comments.length === 0 && (
          <EmptyState icon={<MessageCircle className="h-4 w-4" />} title="No public comments yet" description="Comments can be logged manually above or ingested via the webhook endpoint." />
        )}
        {comments.map((c: any) => {
          const SIcon = SOURCE_ICON[c.source] ?? Mail;
          const SentIcon = SENTIMENT_ICON[c.sentiment] ?? Meh;
          return (
            <Card key={c.id}>
              <CardContent className="space-y-1.5 p-3">
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant={SENTIMENT_VARIANT[c.sentiment] ?? "slate"}><SentIcon className="mr-1 h-3 w-3" />{c.sentiment}</Badge>
                  <Badge variant="outline"><SIcon className="mr-1 h-3 w-3" />{c.source}</Badge>
                  {c.commenter_name && <span className="text-muted-foreground">{c.commenter_name}{c.commenter_org ? ` · ${c.commenter_org}` : ""}</span>}
                  {c.received_date && <span className="text-muted-foreground">· {fmtRelative(c.received_date)}</span>}
                </div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap">{c.body}</div>
                {c.topic_tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {c.topic_tags.map((t: string) => <Badge key={t} variant="outline">{t}</Badge>)}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}

function Stat({ label, value, variant }: any) {
  return (
    <div>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}
