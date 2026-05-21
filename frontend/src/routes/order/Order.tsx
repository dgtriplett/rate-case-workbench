import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gavel, Save, Calendar, TrendingUp, FileSignature } from "lucide-react";

import { api } from "@/lib/api";
import { useCaseContext } from "@/lib/case-context";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate } from "@/lib/format";
import type { CommissionOrder } from "@/lib/types";

const FIELDS: {
  key: keyof CommissionOrder;
  label: string;
  type?: "text" | "date" | "number" | "uuid" | "textarea";
  hint?: string;
}[] = [
  { key: "order_number", label: "Order number", hint: "e.g. Order 26-1184" },
  { key: "issued_date", label: "Issued date", type: "date" },
  { key: "effective_date", label: "Effective date", type: "date" },
  { key: "authorized_revenue_increase_m", label: "Authorized revenue increase ($M)", type: "number" },
  { key: "authorized_roe_pct", label: "Authorized ROE (%)", type: "number" },
  { key: "authorized_equity_pct", label: "Authorized equity (%)", type: "number" },
  { key: "capex_approved_m", label: "Capex approved ($M)", type: "number" },
  { key: "compliance_filings_due", label: "Compliance filings due", type: "date" },
];

export default function OrderRoute() {
  const { caseId, caseData } = useCaseContext();
  const qc = useQueryClient();
  const orderQ = useQuery({
    queryKey: ["cases", caseId, "order"],
    queryFn: () => api.getOrder(caseId),
  });
  const [draft, setDraft] = useState<CommissionOrder>({ case_id: caseId });

  useEffect(() => {
    if (orderQ.data) setDraft(orderQ.data);
    else setDraft({ case_id: caseId });
  }, [orderQ.data, caseId]);

  const saveMut = useMutation({
    mutationFn: () => api.upsertOrder({ ...draft, case_id: caseId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases", caseId, "order"] });
    },
  });

  const requestedRoe = 10.1; // From seed facts; could come from case metadata
  const requestedRevenue = 168.4;

  return (
    <>
      <PageHeader
        eyebrow={<>Order</>}
        title="Commission decision"
        description={`Record the final outcome from the ${caseData?.commission ?? "commission"} on this case. Once issued, downstream compliance filings unlock.`}
        actions={
          <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
            <Save className="h-3.5 w-3.5" />
            {saveMut.isPending ? "Saving…" : draft.id ? "Update" : "Record"}
          </Button>
        }
      />

      <div className="grid grid-cols-12 gap-4 p-6">
        <Card className="col-span-12 md:col-span-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gavel className="h-4 w-4 text-brand-600" />
              Structured outcome
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {FIELDS.map((f) => (
              <div key={f.key} className={f.type === "textarea" ? "col-span-2" : ""}>
                <label className="text-xs font-medium text-slate-700">{f.label}</label>
                <Input
                  type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  step={f.type === "number" ? "0.01" : undefined}
                  value={(draft[f.key] as string | number | null | undefined) ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      [f.key]:
                        f.type === "number" && e.target.value
                          ? parseFloat(e.target.value)
                          : e.target.value || null,
                    }))
                  }
                />
                {f.hint && <div className="mt-0.5 text-[10px] text-muted-foreground">{f.hint}</div>}
              </div>
            ))}
            <div className="col-span-2">
              <label className="text-xs font-medium text-slate-700">Summary</label>
              <Textarea
                value={draft.summary ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
                className="min-h-[120px]"
                placeholder="Key holdings from the commission's order — ROE, rate base adjustments, capex disallowances, rate design changes, etc."
              />
            </div>
          </CardContent>
        </Card>

        <div className="col-span-12 md:col-span-4 space-y-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-brand-600" />
                Outcome vs. request
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Delta
                label="ROE"
                requested={requestedRoe}
                authorized={draft.authorized_roe_pct ?? null}
                unit="%"
              />
              <Delta
                label="Revenue increase"
                requested={requestedRevenue}
                authorized={draft.authorized_revenue_increase_m ?? null}
                unit="$M"
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-brand-600" />
                Important dates
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-xs">
              {draft.issued_date && <div>Issued: <strong>{fmtDate(draft.issued_date)}</strong></div>}
              {draft.effective_date && <div>Effective: <strong>{fmtDate(draft.effective_date)}</strong></div>}
              {draft.compliance_filings_due && (
                <div>Compliance filings due: <strong>{fmtDate(draft.compliance_filings_due)}</strong></div>
              )}
              {!draft.issued_date && !draft.effective_date && (
                <div className="text-muted-foreground">No order yet on this case.</div>
              )}
            </CardContent>
          </Card>
          {draft.full_text_document_id && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSignature className="h-4 w-4 text-brand-600" />
                  Full order text
                </CardTitle>
              </CardHeader>
              <CardContent>
                <a
                  href={api.documentContentUrl(draft.full_text_document_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-medium text-brand-700 hover:underline"
                >
                  Open in UC-permissioned viewer →
                </a>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function Delta({
  label,
  requested,
  authorized,
  unit,
}: {
  label: string;
  requested: number;
  authorized: number | null;
  unit: string;
}) {
  if (authorized == null) {
    return (
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-700">{label}</span>
        <span className="text-muted-foreground">Requested {requested}{unit}</span>
      </div>
    );
  }
  const diff = authorized - requested;
  const pct = requested === 0 ? 0 : (diff / requested) * 100;
  return (
    <div className="rounded-md border border-slate-200 bg-white p-2.5">
      <div className="flex items-center justify-between text-xs font-medium text-slate-800">
        <span>{label}</span>
        <span
          className={diff < 0 ? "text-rose-600" : diff > 0 ? "text-emerald-600" : "text-slate-600"}
        >
          {diff >= 0 ? "+" : ""}{diff.toFixed(2)}{unit} ({pct >= 0 ? "+" : ""}{pct.toFixed(1)}%)
        </span>
      </div>
      <div className="mt-1 text-[10px] text-muted-foreground">
        Requested {requested}{unit} · Authorized <strong>{authorized}{unit}</strong>
      </div>
    </div>
  );
}
