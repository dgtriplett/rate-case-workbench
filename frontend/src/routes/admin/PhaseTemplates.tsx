import { useEffect, useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { GripVertical, Plus, Save } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { PHASE_TYPES, type PhaseType } from "@/lib/types";
import { PHASE_LABELS } from "@/lib/format";

interface Template {
  jurisdiction: string;
  phases: { phase_type: PhaseType; sequence: number; default_days?: number }[];
}

const FALLBACK_TEMPLATES: Template[] = [
  {
    jurisdiction: "MA",
    phases: PHASE_TYPES.map((p, i) => ({
      phase_type: p,
      sequence: i + 1,
      default_days: 30,
    })),
  },
];

export default function AdminPhaseTemplates() {
  const qc = useQueryClient();
  const tplQ = useQuery({
    queryKey: ["admin", "phase-templates"],
    queryFn: () => api.admin.listPhaseTemplates(),
  });

  // Server may not return rich data; fall back to a canonical template
  const templates: Template[] = useMemo(() => {
    const raw = (tplQ.data as Template[] | undefined) ?? [];
    return raw.length ? raw : FALLBACK_TEMPLATES;
  }, [tplQ.data]);

  const [selectedJurisdiction, setSelectedJurisdiction] = useState(
    templates[0]?.jurisdiction ?? "MA",
  );
  const selected =
    templates.find((t) => t.jurisdiction === selectedJurisdiction) ??
    templates[0];
  const [phases, setPhases] = useState(selected?.phases ?? []);

  useEffect(() => {
    setPhases(selected?.phases ?? []);
  }, [selected]);

  const saveMut = useMutation({
    mutationFn: () =>
      api.admin.upsertPhaseTemplate({
        jurisdiction: selectedJurisdiction,
        phases,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "phase-templates"] });
    },
  });

  function move(idx: number, dir: -1 | 1) {
    setPhases((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next.map((p, i) => ({ ...p, sequence: i + 1 }));
    });
  }

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Phase templates"
        description="Default phase sequences applied when new cases are created in each jurisdiction."
        actions={
          <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
            <Save className="h-3.5 w-3.5" />
            Save template
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Jurisdiction
            </h3>
            <Select
              value={selectedJurisdiction}
              onValueChange={setSelectedJurisdiction}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.jurisdiction} value={t.jurisdiction}>
                    {t.jurisdiction}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="mt-3 text-xs text-muted-foreground">
              Add jurisdictions in the Cases tab; their first case creation
              seeds a template here.
            </div>
            <Button variant="outline" size="sm" className="mt-3 w-full" disabled>
              <Plus className="h-3.5 w-3.5" />
              New jurisdiction template
            </Button>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardContent className="p-0">
            <div className="border-b border-border bg-slate-50/50 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Phase order
            </div>
            <ul>
              {phases.map((p, i) => (
                <li
                  key={p.phase_type}
                  className="flex items-center gap-3 border-b border-border px-4 py-2.5 last:border-0"
                >
                  <GripVertical className="h-4 w-4 text-slate-300" />
                  <div className="flex h-6 w-6 items-center justify-center rounded bg-slate-100 text-[10px] font-semibold text-slate-700">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-800">
                      {PHASE_LABELS[p.phase_type]}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {p.phase_type}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      {p.default_days ?? 30}d default
                    </Badge>
                    <div className="flex flex-col">
                      <button
                        onClick={() => move(i, -1)}
                        className="px-1 text-xs text-slate-500 hover:text-slate-800"
                      >
                        ▲
                      </button>
                      <button
                        onClick={() => move(i, 1)}
                        className="px-1 text-xs text-slate-500 hover:text-slate-800"
                      >
                        ▼
                      </button>
                    </div>
                    <Input
                      type="number"
                      className="w-20"
                      value={p.default_days ?? 30}
                      onChange={(e) =>
                        setPhases((prev) =>
                          prev.map((pp, idx) =>
                            idx === i
                              ? { ...pp, default_days: Number(e.target.value) }
                              : pp,
                          ),
                        )
                      }
                    />
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
