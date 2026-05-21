import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Power, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const TRIGGERS = [
  { v: "dr_due_in_days", label: "DR due in N days" },
  { v: "dr_overdue", label: "DR overdue" },
  { v: "position_logged_over_threshold", label: "Intervenor position logged ≥ $XM" },
  { v: "response_filed", label: "Response filed" },
  { v: "order_issued", label: "Order issued" },
];
const ACTIONS = [
  { v: "notify", label: "Post notification" },
  { v: "post_audit", label: "Post to audit log" },
];

export default function AdminAutomation() {
  const qc = useQueryClient();
  const rulesQ = useQuery({ queryKey: ["admin", "automation"], queryFn: () => api.listAutomationRules() });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [trigger, setTrigger] = useState("dr_due_in_days");
  const [triggerConfig, setTriggerConfig] = useState("2");
  const [action, setAction] = useState("post_audit");

  const createMut = useMutation({
    mutationFn: () =>
      api.createAutomationRule({
        name, description,
        trigger_kind: trigger,
        trigger_config:
          trigger === "dr_due_in_days" ? { days: parseInt(triggerConfig) || 2 } :
          trigger === "position_logged_over_threshold" ? { threshold_m: parseFloat(triggerConfig) || 25.0 } : {},
        action_kind: action,
        action_config: {},
        enabled: true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "automation"] });
      setName(""); setDescription("");
    },
  });
  const toggleMut = useMutation({
    mutationFn: ({ id, body }: any) => api.updateAutomationRule(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "automation"] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteAutomationRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "automation"] }),
  });
  const runMut = useMutation({
    mutationFn: () => api.evaluateAutomation(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "automation"] }),
  });

  const rules = rulesQ.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow={<>Admin · Automation</>}
        title="Workflow automation rules"
        description="When-this / then-that rules that codify your team's regulatory practice. Each rule has a trigger and an action; rules are evaluated by a scheduled Databricks Job (or on demand via 'Run now')."
        actions={
          <Button variant="outline" size="sm" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
            <Play className="h-3.5 w-3.5" />
            {runMut.isPending ? "Evaluating…" : "Run all rules now"}
          </Button>
        }
      />
      <div className="space-y-4 p-6">
        <Card>
          <CardContent className="p-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Create new rule</div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-5">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Rule name (e.g. Escalate near-due DRs)" />
              <Select value={trigger} onValueChange={setTrigger}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TRIGGERS.map((t) => (<SelectItem key={t.v} value={t.v}>{t.label}</SelectItem>))}</SelectContent>
              </Select>
              {(trigger === "dr_due_in_days" || trigger === "position_logged_over_threshold") && (
                <Input value={triggerConfig} onChange={(e) => setTriggerConfig(e.target.value)} placeholder={trigger === "dr_due_in_days" ? "Days" : "Threshold ($M)"} />
              )}
              <Select value={action} onValueChange={setAction}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{ACTIONS.map((a) => (<SelectItem key={a.v} value={a.v}>{a.label}</SelectItem>))}</SelectContent>
              </Select>
              <Button disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}>
                <Plus className="h-3.5 w-3.5" /> Create rule
              </Button>
            </div>
            <Input className="mt-2" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
          </CardContent>
        </Card>

        {rulesQ.isLoading && <Skeleton className="h-32" />}
        {rules.map((r: any) => (
          <Card key={r.id}>
            <CardContent className="flex items-center justify-between gap-3 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{r.name}</span>
                  <Badge variant={r.enabled ? "success" : "slate"}>{r.enabled ? "Enabled" : "Disabled"}</Badge>
                  <Badge variant="outline">{r.trigger_kind}</Badge>
                  <Badge variant="outline">→ {r.action_kind}</Badge>
                </div>
                {r.description && <div className="mt-0.5 text-[11px] text-muted-foreground">{r.description}</div>}
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  fired {r.fire_count}× · last {r.last_fired_at ? new Date(r.last_fired_at).toLocaleString() : "never"}
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={() => toggleMut.mutate({ id: r.id, body: { ...r, enabled: !r.enabled } })}>
                <Power className="h-3.5 w-3.5" /> {r.enabled ? "Disable" : "Enable"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => deleteMut.mutate(r.id)}>
                <Trash2 className="h-3.5 w-3.5 text-rose-600" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
