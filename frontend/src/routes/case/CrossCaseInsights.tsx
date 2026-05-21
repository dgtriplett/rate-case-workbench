import { useQuery } from "@tanstack/react-query";
import { Lightbulb, Library } from "lucide-react";
import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty";

export default function CrossCaseInsights() {
  const { caseId } = useCaseContext();
  const q = useQuery({
    queryKey: ["cases", caseId, "cross-case"],
    queryFn: () => api.getCrossCaseInsights(caseId),
  });
  const data = q.data;
  return (
    <>
      <PageHeader
        eyebrow={<>Cross-case insights</>}
        title="Jurisdictional precedents that apply here"
        description="Surfaces positions taken in prior cases in this jurisdiction that match the open intervenor positions and topics on this case — with how the commission ruled."
      />
      <div className="space-y-4 p-6">
        {q.isLoading && <Skeleton className="h-64" />}
        {data?.summary_text && (
          <Card className="border-brand-200 bg-gradient-to-br from-brand-50 via-white to-white">
            <CardContent className="flex items-start gap-2 p-4">
              <Lightbulb className="mt-0.5 h-4 w-4 text-brand-600" />
              <div className="text-sm leading-relaxed text-slate-800">{data.summary_text}</div>
            </CardContent>
          </Card>
        )}
        {data?.analogues?.length === 0 && !q.isLoading && (
          <EmptyState icon={<Library className="h-4 w-4" />} title="No analogues found yet" description="As intervenor positions are logged and prior-case memory grows, precedents will appear here." />
        )}
        {data?.analogues?.map((a: any, i: number) => (
          <Card key={i}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Library className="h-4 w-4 text-brand-600" />
                {a.prior_case_docket} — {a.prior_case_name}
                <Badge variant="outline">{a.topic_key}</Badge>
                <Badge variant="slate">{Math.round((a.confidence ?? 0) * 100)}% conf.</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs">
              <div className="rounded-md border border-slate-200 bg-white p-2.5">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Prior position</div>
                <p className="mt-1 leading-relaxed text-slate-700">{a.fact_text}</p>
              </div>
              {a.outcome && (
                <div className="rounded-md border border-emerald-200 bg-emerald-50/40 p-2.5">
                  <div className="text-[10px] uppercase tracking-wide text-emerald-700">Commission outcome</div>
                  <p className="mt-1 leading-relaxed text-slate-700">{a.outcome}</p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
