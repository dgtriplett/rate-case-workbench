import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Flag } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminFeatureFlags() {
  const qc = useQueryClient();
  const flagsQ = useQuery({
    queryKey: ["admin", "feature-flags"],
    queryFn: () => api.admin.listFeatureFlags(),
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.admin.updateFeatureFlag(id, enabled),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "feature-flags"] }),
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Feature flags"
        description="Toggle modules globally or per-case. Flags control optional surfaces — Genie pinning, position checking, agent autosave, etc."
      />

      <div className="p-6">
        {flagsQ.isLoading && <Skeleton className="h-40" />}
        {!flagsQ.isLoading && (flagsQ.data ?? []).length === 0 && (
          <EmptyState
            icon={<Flag className="h-4 w-4" />}
            title="No feature flags defined."
            description="Flags are created server-side. Once defined, they appear here for toggling."
          />
        )}

        <div className="space-y-2">
          {(flagsQ.data ?? []).map((f) => (
            <Card key={f.id}>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                      <Flag className="h-3.5 w-3.5" />
                    </div>
                    <div className="font-mono text-sm font-medium text-slate-900">
                      {f.key}
                    </div>
                    <Badge variant="outline">{f.scope}</Badge>
                  </div>
                  {f.description && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {f.description}
                    </p>
                  )}
                </div>
                <Switch
                  checked={f.enabled}
                  onCheckedChange={(v) =>
                    toggle.mutate({ id: f.id, enabled: v })
                  }
                />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
