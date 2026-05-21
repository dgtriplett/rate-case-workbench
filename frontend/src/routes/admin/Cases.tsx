import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Archive,
  Briefcase,
  ChevronRight,
  Plus,
} from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate } from "@/lib/format";
import type { CaseCreate } from "@/lib/types";

export default function AdminCases() {
  const qc = useQueryClient();
  const casesQ = useQuery({
    queryKey: ["admin", "cases"],
    queryFn: () => api.listCases(),
  });

  const archiveMut = useMutation({
    mutationFn: (id: string) => api.admin.archiveCase(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "cases"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Cases"
        description="Create new rate cases, configure metadata, and archive completed ones."
        actions={
          <NewCaseDialog>
            <Button>
              <Plus className="h-3.5 w-3.5" />
              New case
            </Button>
          </NewCaseDialog>
        }
      />

      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-white">
          {casesQ.isLoading ? (
            <Skeleton className="h-64" />
          ) : (casesQ.data ?? []).length === 0 ? (
            <EmptyState
              icon={<Briefcase className="h-4 w-4" />}
              title="No cases yet."
              action={
                <NewCaseDialog>
                  <Button>
                    <Plus className="h-3.5 w-3.5" />
                    Create a case
                  </Button>
                </NewCaseDialog>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case</TableHead>
                  <TableHead className="w-40">Docket</TableHead>
                  <TableHead className="w-40">Jurisdiction</TableHead>
                  <TableHead className="w-32">Status</TableHead>
                  <TableHead className="w-32">Filed</TableHead>
                  <TableHead className="w-32">Decision</TableHead>
                  <TableHead className="w-28"> </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(casesQ.data ?? []).map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <div className="font-medium text-slate-800">{c.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {c.utility_name}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {c.docket_number}
                    </TableCell>
                    <TableCell className="text-xs">{c.jurisdiction}</TableCell>
                    <TableCell>
                      <Badge variant="brand">
                        {c.status.replaceAll("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {fmtDate(c.filed_date)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {fmtDate(c.target_decision_date)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Link
                          to="/cases/$caseId"
                          params={{ caseId: c.id }}
                          className="rounded-md border border-border px-2 py-1 text-xs hover:bg-slate-50"
                        >
                          Open
                        </Link>
                        <button
                          onClick={() => archiveMut.mutate(c.id)}
                          className="rounded-md border border-border p-1 text-slate-500 hover:bg-slate-50"
                          title="Archive"
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </button>
                        <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </>
  );
}

function NewCaseDialog({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(1);
  const qc = useQueryClient();
  const [form, setForm] = useState<CaseCreate>({
    name: "",
    docket_number: "",
    jurisdiction: "",
    commission: "",
    utility_name: "",
    case_type: "general_rate_case",
  });

  const createMut = useMutation({
    mutationFn: () => api.createCase(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "cases"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      setOpen(false);
      setStep(1);
    },
  });

  function patch<K extends keyof CaseCreate>(k: K, v: CaseCreate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Create a new case · step {step} of 2</DialogTitle>
          <DialogDescription>
            Configure case metadata. The default jurisdiction phase template
            will be applied automatically.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium">Case name</label>
              <Input
                value={form.name}
                onChange={(e) => patch("name", e.target.value)}
                placeholder="Eversource 2026 General Rate Case"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Docket #</label>
              <Input
                value={form.docket_number}
                onChange={(e) => patch("docket_number", e.target.value)}
                placeholder="DPU 26-01"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Case type</label>
              <Input
                value={form.case_type}
                onChange={(e) => patch("case_type", e.target.value)}
                placeholder="general_rate_case"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Jurisdiction</label>
              <Input
                value={form.jurisdiction}
                onChange={(e) => patch("jurisdiction", e.target.value)}
                placeholder="MA"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Commission</label>
              <Input
                value={form.commission}
                onChange={(e) => patch("commission", e.target.value)}
                placeholder="Massachusetts DPU"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium">Utility</label>
              <Input
                value={form.utility_name}
                onChange={(e) => patch("utility_name", e.target.value)}
                placeholder="Eversource Energy"
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium">Filed date</label>
                <Input
                  type="date"
                  value={form.filed_date ?? ""}
                  onChange={(e) => patch("filed_date", e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium">
                  Target decision date
                </label>
                <Input
                  type="date"
                  value={form.target_decision_date ?? ""}
                  onChange={(e) =>
                    patch("target_decision_date", e.target.value)
                  }
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium">Description</label>
              <Textarea
                value={form.description ?? ""}
                onChange={(e) => patch("description", e.target.value)}
                placeholder="Short summary of the case scope, intervenors, and key issues."
                rows={4}
              />
            </div>
          </div>
        )}

        <DialogFooter>
          {step > 1 && (
            <Button variant="outline" onClick={() => setStep(step - 1)}>
              Back
            </Button>
          )}
          {step < 2 ? (
            <Button onClick={() => setStep(step + 1)}>Next</Button>
          ) : (
            <Button
              onClick={() => createMut.mutate()}
              disabled={
                !form.name ||
                !form.docket_number ||
                !form.jurisdiction ||
                createMut.isPending
              }
            >
              Create case
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
