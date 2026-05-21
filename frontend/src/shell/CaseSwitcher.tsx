import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { CaseOut, CaseStatus } from "@/lib/types";

const STAGE_LABEL: Record<CaseStatus, string> = {
  pre_filing: "Pre-filing",
  active: "Active",
  on_hold: "On hold",
  closed: "Complete",
};

const STAGE_VARIANT: Record<CaseStatus, "warning" | "brand" | "slate" | "success"> = {
  pre_filing: "warning",
  active: "brand",
  on_hold: "slate",
  closed: "success",
};
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";

export function CaseSwitcher() {
  const navigate = useNavigate();
  const params = useParams({ strict: false }) as { caseId?: string };
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");

  const { data: cases = [] } = useQuery<CaseOut[]>({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
  });

  const current = useMemo(
    () => cases.find((c) => c.id === params.caseId),
    [cases, params.caseId],
  );

  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return cases;
    return cases.filter(
      (c) =>
        c.name.toLowerCase().includes(f) ||
        c.docket_number.toLowerCase().includes(f) ||
        c.jurisdiction.toLowerCase().includes(f) ||
        c.utility_name.toLowerCase().includes(f),
    );
  }, [cases, filter]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="h-9 max-w-[420px] justify-between gap-2 border-slate-200 bg-white px-3"
        >
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-brand-50 text-[10px] font-semibold text-brand-700">
              {current ? current.jurisdiction.slice(0, 2).toUpperCase() : "—"}
            </div>
            <span className="truncate font-medium">
              {current ? current.name : "Select case"}
            </span>
            {current && (
              <>
                <Badge variant="outline" className="hidden sm:inline-flex">
                  {current.docket_number}
                </Badge>
                <Badge variant={STAGE_VARIANT[current.status as CaseStatus]} className="hidden md:inline-flex">
                  {STAGE_LABEL[current.status as CaseStatus]}
                </Badge>
              </>
            )}
          </div>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[420px] p-0"
        sideOffset={6}
      >
        <div className="border-b border-border p-2">
          <Input
            placeholder="Search cases by name, docket, jurisdiction…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="h-9"
          />
        </div>
        <div className="max-h-72 overflow-y-auto p-1 scrollbar-thin">
          {filtered.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              No cases match.
            </div>
          )}
          {filtered.map((c) => {
            const selected = c.id === current?.id;
            return (
              <button
                key={c.id}
                onClick={() => {
                  setOpen(false);
                  navigate({
                    to: "/cases/$caseId",
                    params: { caseId: c.id },
                  });
                }}
                className={cn(
                  "w-full rounded-md px-2.5 py-2 text-left hover:bg-slate-50",
                  selected && "bg-brand-50/60",
                )}
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-50 text-[11px] font-semibold text-brand-700">
                    {c.jurisdiction.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {c.name}
                      </span>
                      <Badge variant={STAGE_VARIANT[c.status as CaseStatus]}>
                        {STAGE_LABEL[c.status as CaseStatus]}
                      </Badge>
                      {selected && (
                        <Check className="h-3.5 w-3.5 shrink-0 text-brand-600" />
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {c.docket_number} · {c.utility_name} ·{" "}
                      {c.jurisdiction}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
        <div className="border-t border-border p-2">
          <Link to="/admin/cases" onClick={() => setOpen(false)}>
            <Button variant="ghost" size="sm" className="w-full justify-start">
              <Plus className="h-3.5 w-3.5" />
              Create a new case
            </Button>
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  );
}
