import { useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Brain, Plus, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
import type { ModelConfigOut } from "@/lib/types";

const TASKS = [
  "drafter",
  "summarizer",
  "position_checker",
  "redactor",
] as const;
type Task = (typeof TASKS)[number];

const TASK_LABELS: Record<Task, string> = {
  drafter: "Response drafter",
  summarizer: "Document summarizer",
  position_checker: "Position consistency",
  redactor: "Confidential redactor",
};

export default function AdminModels() {
  const modelsQ = useQuery({
    queryKey: ["admin", "models"],
    queryFn: () => api.admin.listModels(),
  });
  const models = modelsQ.data ?? [];

  const groupedByTask = useMemo(() => {
    const map = new Map<string, ModelConfigOut[]>();
    for (const t of TASKS) map.set(t, []);
    for (const m of models) {
      const list = map.get(m.name) ?? [];
      list.push(m);
      map.set(m.name, list);
    }
    return map;
  }, [models]);

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Model endpoints"
        description="Map serving endpoints to agent tasks. Drafting, summarization, position checking, and redaction can each use a different model."
        actions={
          <NewModelDialog>
            <Button>
              <Plus className="h-3.5 w-3.5" />
              Add endpoint
            </Button>
          </NewModelDialog>
        }
      />

      <div className="space-y-4 p-6">
        {modelsQ.isLoading && <Skeleton className="h-40" />}

        {TASKS.map((task) => {
          const items = groupedByTask.get(task) ?? [];
          return (
            <Card key={task}>
              <CardContent className="p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                      <Brain className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">
                        {TASK_LABELS[task]}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Task key: <span className="font-mono">{task}</span>
                      </div>
                    </div>
                  </div>
                  <NewModelDialog defaultTask={task}>
                    <Button variant="outline" size="sm">
                      <Plus className="h-3.5 w-3.5" />
                      Map endpoint
                    </Button>
                  </NewModelDialog>
                </div>

                {items.length === 0 ? (
                  <EmptyState
                    title="No endpoint mapped"
                    description="This task will fall back to the default workspace model."
                  />
                ) : (
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {items.map((m) => (
                      <ModelCard key={m.id} model={m} />
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

function ModelCard({ model }: { model: ModelConfigOut }) {
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: () => api.admin.deleteModel(model.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "models"] }),
  });
  return (
    <div className="flex items-start justify-between gap-2 rounded-md border border-slate-200 bg-white p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Badge variant={model.is_default ? "brand" : "slate"}>
            {model.is_default ? "Default" : model.scope}
          </Badge>
        </div>
        <div className="mt-1 font-mono text-xs text-slate-800">
          {model.endpoint}
        </div>
        {Object.keys(model.params ?? {}).length > 0 && (
          <details className="mt-1">
            <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-muted-foreground">
              Params
            </summary>
            <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-1.5 text-[10px] font-mono text-slate-700">
              {JSON.stringify(model.params, null, 2)}
            </pre>
          </details>
        )}
      </div>
      <button
        onClick={() => del.mutate()}
        className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50"
        title="Remove"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function NewModelDialog({
  children,
  defaultTask,
}: {
  children: React.ReactNode;
  defaultTask?: Task;
}) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const [task, setTask] = useState<Task>(defaultTask ?? "drafter");
  const [endpoint, setEndpoint] = useState("");
  const [paramsText, setParamsText] = useState("{}");
  const [isDefault, setIsDefault] = useState(true);

  const upsert = useMutation({
    mutationFn: () => {
      let params: Record<string, unknown> = {};
      try {
        params = JSON.parse(paramsText);
      } catch {
        params = {};
      }
      return api.admin.upsertModel({
        name: task,
        endpoint,
        params,
        is_default: isDefault,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "models"] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Map a model endpoint</DialogTitle>
          <DialogDescription>
            Use any Databricks serving endpoint — Foundation Models, custom
            fine-tunes, or external models gated by AI Gateway.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium">Task</label>
              <Select value={task} onValueChange={(v) => setTask(v as Task)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TASKS.map((t) => (
                    <SelectItem key={t} value={t}>
                      {TASK_LABELS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 accent-brand-500"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                />
                Default for task
              </label>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">Endpoint</label>
            <Input
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="databricks-claude-sonnet-4-5"
              className="font-mono"
            />
          </div>
          <div>
            <label className="text-xs font-medium">Params (JSON)</label>
            <textarea
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
              className="min-h-[100px] w-full rounded-md border border-slate-200 bg-white p-2 font-mono text-xs"
              placeholder={`{"temperature": 0.2, "max_tokens": 4096}`}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => upsert.mutate()}
            disabled={!endpoint || upsert.isPending}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
