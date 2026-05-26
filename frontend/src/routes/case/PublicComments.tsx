import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  FileText,
  Frown,
  Globe,
  Mail,
  Meh,
  MessageCircle,
  Radio,
  Smile,
  Sparkles,
} from "lucide-react";
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
import { fmtRelative } from "@/lib/format";

const SENTIMENT_VARIANT: Record<string, any> = {
  positive: "success", negative: "danger", neutral: "slate", mixed: "warning",
};
const SENTIMENT_ICON: Record<string, any> = {
  positive: Smile, negative: Frown, neutral: Meh, mixed: Meh,
};
const SOURCE_ICON: Record<string, any> = {
  email: Mail, portal: Globe, letter: FileText, oral: MessageCircle, social_media: Radio,
};
const PLATFORM_COLOR: Record<string, string> = {
  twitter: "bg-sky-100 text-sky-800 ring-sky-200",
  facebook: "bg-blue-100 text-blue-800 ring-blue-200",
  reddit: "bg-orange-100 text-orange-800 ring-orange-200",
  nextdoor: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  youtube: "bg-rose-100 text-rose-800 ring-rose-200",
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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: () => api.createPublicComment({
      case_id: caseId, source, commenter_name: name || null, commenter_org: org || null, body,
      received_date: new Date().toISOString().slice(0, 10),
    }),
    onSuccess: () => {
      setName(""); setOrg(""); setBody(""); setErrorMsg(null); setOkMsg("Comment logged.");
      qc.invalidateQueries({ queryKey: ["cases", caseId, "comments"] });
      qc.invalidateQueries({ queryKey: ["cases", caseId, "comments-summary"] });
      setTimeout(() => setOkMsg(null), 2500);
    },
    onError: (err: any) => setErrorMsg(err?.message ? `Failed to log comment: ${err.message}` : "Failed to log comment"),
  });

  const ingestMut = useMutation({
    mutationFn: () => api.ingestSocialComments(caseId, { platforms: ["twitter", "facebook", "reddit", "nextdoor", "youtube"], count: 8 }),
    onSuccess: (res: any) => {
      setErrorMsg(null);
      const total = res?.inserted ?? 0;
      const platforms = res?.by_platform ? Object.entries(res.by_platform).map(([p, n]) => `${p}: ${n}`).join(", ") : "";
      setOkMsg(`Ingested ${total} social comments${platforms ? ` (${platforms})` : ""}.`);
      qc.invalidateQueries({ queryKey: ["cases", caseId, "comments"] });
      qc.invalidateQueries({ queryKey: ["cases", caseId, "comments-summary"] });
      setTimeout(() => setOkMsg(null), 4000);
    },
    onError: (err: any) => setErrorMsg(err?.message ? `Social ingestion failed: ${err.message}` : "Social ingestion failed"),
  });

  const comments = q.data ?? [];
  const summary = summaryQ.data;

  return (
    <>
      <PageHeader
        eyebrow={<>Public engagement</>}
        title="Public comments"
        description="Comments from email, the commission portal, letters, oral testimony at public hearings, and social media. Each one is auto-classified for sentiment + topic by Claude. In production, social ingestion would call platform APIs (Twitter/X, Facebook Graph, Reddit, Nextdoor, YouTube) or a social-listening vendor like Brandwatch / Sprinklr / Talkwalker."
        actions={
          <Button size="sm" onClick={() => ingestMut.mutate()} disabled={ingestMut.isPending}>
            <Sparkles className="h-3.5 w-3.5" />{" "}
            {ingestMut.isPending ? "Ingesting…" : "Pull from social media"}
          </Button>
        }
      />
      <div className="p-6 space-y-4">
        {errorMsg && (
          <Card className="border-red-200 bg-red-50/50">
            <CardContent className="flex items-center gap-2 p-3 text-xs text-red-800">
              <AlertCircle className="h-3.5 w-3.5" /> {errorMsg}
            </CardContent>
          </Card>
        )}
        {okMsg && (
          <Card className="border-emerald-200 bg-emerald-50/50">
            <CardContent className="p-3 text-xs text-emerald-900">{okMsg}</CardContent>
          </Card>
        )}

        {summary && (
          <Card>
            <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3 p-3">
              <Stat label="Total" value={summary.total} />
              <Stat label="Positive" value={summary.by_sentiment?.positive ?? 0} />
              <Stat label="Negative" value={summary.by_sentiment?.negative ?? 0} />
              <Stat label="Mixed" value={summary.by_sentiment?.mixed ?? 0} />
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
                  <SelectItem value="social_media">Social media (manual)</SelectItem>
                </SelectContent>
              </Select>
              <Button disabled={!body.trim() || createMut.isPending} onClick={() => createMut.mutate()}>
                {createMut.isPending ? "Logging…" : "Log comment"}
              </Button>
            </div>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="min-h-[100px]"
              placeholder="Paste or type the comment text — sentiment + topics auto-classified by AI on save."
            />
            <div className="text-[11px] text-muted-foreground">
              Tip: click <strong>Pull from social media</strong> at the top to ingest a fresh batch of platform comments
              (Twitter/X, Facebook, Reddit, Nextdoor, YouTube) for this case.
            </div>
          </CardContent>
        </Card>

        {q.isLoading && <Skeleton className="h-32" />}
        {!q.isLoading && comments.length === 0 && (
          <EmptyState
            icon={<MessageCircle className="h-4 w-4" />}
            title="No public comments yet"
            description="Log a comment manually above, or click 'Pull from social media' to simulate a social-listening ingestion."
          />
        )}
        {comments.map((c: any) => {
          const SIcon = SOURCE_ICON[c.source] ?? Mail;
          const SentIcon = SENTIMENT_ICON[c.sentiment] ?? Meh;
          const platformClass = c.platform ? PLATFORM_COLOR[c.platform] : null;
          return (
            <Card key={c.id}>
              <CardContent className="space-y-1.5 p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant={SENTIMENT_VARIANT[c.sentiment] ?? "slate"}>
                    <SentIcon className="mr-1 h-3 w-3" />
                    {c.sentiment}
                  </Badge>
                  <Badge variant="outline">
                    <SIcon className="mr-1 h-3 w-3" />
                    {c.source === "social_media" ? "social" : c.source}
                  </Badge>
                  {c.platform && (
                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${platformClass ?? "bg-slate-100 text-slate-700 ring-slate-200"}`}>
                      {c.platform}
                    </span>
                  )}
                  {(c.commenter_name || c.source_handle) && (
                    <span className="text-muted-foreground">
                      {c.commenter_name || ""}
                      {c.source_handle ? ` (${c.source_handle})` : ""}
                      {c.commenter_org ? ` · ${c.commenter_org}` : ""}
                    </span>
                  )}
                  {c.received_date && <span className="text-muted-foreground">· {fmtRelative(c.received_date)}</span>}
                </div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap">{c.body}</div>
                {c.topic_tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {c.topic_tags.map((t: string) => (
                      <Badge key={t} variant="outline">{t}</Badge>
                    ))}
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

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}
