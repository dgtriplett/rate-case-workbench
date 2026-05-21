import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Key, Plug, Plus, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

interface Integration {
  id: string;
  kind: string;
  label: string;
  secret_ref?: string;
  status?: "ok" | "needs_config" | "error";
}

const KINDS = [
  { value: "commission_efiling", label: "Commission e-filing portal" },
  { value: "doc_storage", label: "Document storage (S3/UC Volume)" },
  { value: "sso", label: "SSO / OIDC" },
  { value: "mlflow", label: "MLflow tracking" },
  { value: "smtp", label: "SMTP notifications" },
  { value: "webhook", label: "Webhook" },
];

export default function AdminIntegrations() {
  const qc = useQueryClient();
  const intQ = useQuery({
    queryKey: ["admin", "integrations"],
    queryFn: () => api.admin.listIntegrations() as Promise<Integration[]>,
  });

  const items = intQ.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Integrations"
        description="Configure secrets and external connections. Secret values are managed via the Databricks secrets API and never displayed here."
        actions={
          <NewIntegrationDialog>
            <Button>
              <Plus className="h-3.5 w-3.5" />
              Add integration
            </Button>
          </NewIntegrationDialog>
        }
      />
      <div className="p-6">
        {intQ.isLoading && <Skeleton className="h-40" />}
        {!intQ.isLoading && items.length === 0 && (
          <EmptyState
            icon={<Plug className="h-4 w-4" />}
            title="No integrations configured."
            description="Connect commission e-filing, document storage, SMTP, MLflow, and other systems."
          />
        )}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((it) => (
            <Card key={it.id}>
              <CardContent className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                      <Plug className="h-3.5 w-3.5" />
                    </div>
                    <div className="text-sm font-semibold">{it.label}</div>
                    <Badge variant="outline">{it.kind}</Badge>
                    {it.status === "ok" && (
                      <Badge variant="success">connected</Badge>
                    )}
                    {it.status === "needs_config" && (
                      <Badge variant="warning">needs config</Badge>
                    )}
                    {it.status === "error" && (
                      <Badge variant="danger">error</Badge>
                    )}
                  </div>
                  {it.secret_ref && (
                    <div className="mt-1 inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
                      <Key className="h-3 w-3" /> {it.secret_ref}
                    </div>
                  )}
                </div>
                <button className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}

function NewIntegrationDialog({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState(KINDS[0].value);
  const [label, setLabel] = useState("");
  const [secretRef, setSecretRef] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      api.admin.upsertIntegration({
        kind,
        label,
        secret_ref: secretRef || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "integrations"] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add integration</DialogTitle>
          <DialogDescription>
            Configure a connection. Secret values are stored in the Databricks
            secrets API; reference them by scope/key here.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium">Kind</label>
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k.value} value={k.value}>
                      {k.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium">Label</label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="MA DPU portal"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">Secret reference</label>
            <Input
              value={secretRef}
              onChange={(e) => setSecretRef(e.target.value)}
              placeholder="secret-scope/key (e.g. rcw/portal_token)"
              className="font-mono"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mut.mutate()}
            disabled={!label || mut.isPending}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
