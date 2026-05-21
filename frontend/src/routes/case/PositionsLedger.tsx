import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { AlertTriangle, Database, FileText, GitCompare, ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";

const KIND_ICON: Record<string, any> = {
  filed_response: FileText,
  testimony: ScrollText,
  brief: ScrollText,
  agent_memory: Database,
};

export default function PositionsLedger() {
  const { caseId } = useCaseContext();
  const q = useQuery({
    queryKey: ["cases", caseId, "positions-ledger"],
    queryFn: () => api.getPositionsLedger(caseId),
  });
  const data = q.data;

  return (
    <>
      <PageHeader
        eyebrow={<>Positions ledger</>}
        title="Position consistency ledger"
        description="Every position this utility has taken across filed responses, testimony, briefs, and agent memory — grouped by topic. AI scans for drift across artifacts and flags inconsistencies."
      />
      <div className="space-y-4 p-6">
        {q.isLoading && <Skeleton className="h-64" />}
        {!q.isLoading && (!data || data.topics?.length === 0) && (
          <EmptyState icon={<GitCompare className="h-4 w-4" />} title="No positions on file yet" description="Once responses are filed and testimony is approved, the ledger will populate." />
        )}
        {data?.topics?.map((t: any) => (
          <Card key={t.topic_key}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="text-sm">{t.topic_key.replace(/_/g, " ")}</span>
                <Badge variant="outline">{t.statements.length} statements</Badge>
              </CardTitle>
              {t.drift_warnings?.length > 0 && (
                <div className="mt-2 space-y-1 rounded-md border border-amber-200 bg-amber-50 p-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-amber-800">
                    <AlertTriangle className="h-3 w-3" /> Drift detected
                  </div>
                  {t.drift_warnings.map((w: string, i: number) => (
                    <div key={i} className="text-[11px] leading-snug text-amber-900">• {w}</div>
                  ))}
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-2">
              {t.statements.map((s: any) => {
                const Icon = KIND_ICON[s.artifact_kind] ?? FileText;
                return (
                  <Link key={s.artifact_id} to={s.url} className="flex items-start gap-2 rounded-md border border-slate-200 bg-white p-2.5 hover:border-brand-300">
                    <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-xs font-medium text-slate-800">
                        {s.artifact_title}
                        <Badge variant="slate">{s.artifact_kind.replace("_", " ")}</Badge>
                        {s.status && <Badge variant="outline">{s.status}</Badge>}
                      </div>
                      <p className="mt-1 line-clamp-3 text-[11px] text-slate-600">{s.excerpt}</p>
                      {s.issued_or_filed_date && (
                        <div className="mt-0.5 text-[10px] text-muted-foreground">filed/issued {s.issued_or_filed_date}</div>
                      )}
                    </div>
                  </Link>
                );
              })}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
