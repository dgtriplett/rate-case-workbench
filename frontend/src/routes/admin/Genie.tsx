import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { MessagesSquare, Plus, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { RoleKey } from "@/lib/types";

const ALL_ROLES: RoleKey[] = [
  "case_manager",
  "reviewer",
  "approver",
  "witness",
  "viewer",
  "admin",
];

export default function AdminGenie() {
  const qc = useQueryClient();
  const roomsQ = useQuery({
    queryKey: ["admin", "genie"],
    queryFn: () => api.admin.listGenieRooms(),
  });
  const casesQ = useQuery({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.admin.deleteGenieRoom(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "genie"] }),
  });

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Genie rooms"
        description="Register Genie spaces the agent can query during drafting. Each room can be scoped to a case and gated by role."
        actions={
          <RegisterDialog cases={casesQ.data ?? []}>
            <Button>
              <Plus className="h-3.5 w-3.5" />
              Register room
            </Button>
          </RegisterDialog>
        }
      />

      <div className="p-6">
        {roomsQ.isLoading && <Skeleton className="h-40" />}
        {!roomsQ.isLoading && (roomsQ.data ?? []).length === 0 && (
          <EmptyState
            icon={<MessagesSquare className="h-4 w-4" />}
            title="No Genie rooms registered."
            description="Register a Genie space so the agent can ground numerical answers in your governed tables."
          />
        )}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {(roomsQ.data ?? []).map((r) => (
            <Card key={r.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-violet-50 text-violet-700">
                        <MessagesSquare className="h-3.5 w-3.5" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {r.label}
                        </div>
                        <div className="font-mono text-[11px] text-muted-foreground">
                          {r.room_id}
                        </div>
                      </div>
                    </div>
                    {r.description && (
                      <p className="mt-2 text-xs text-muted-foreground">
                        {r.description}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1">
                      {r.case_id ? (
                        <Badge variant="brand">case-scoped</Badge>
                      ) : (
                        <Badge variant="slate">global</Badge>
                      )}
                      {r.allowed_roles.map((role) => (
                        <Badge key={role} variant="outline">
                          {role}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => del.mutate(r.id)}
                    className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}

function RegisterDialog({
  children,
  cases,
}: {
  children: React.ReactNode;
  cases: { id: string; name: string }[];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [roomId, setRoomId] = useState("");
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [caseId, setCaseId] = useState<string | undefined>();
  const [roles, setRoles] = useState<RoleKey[]>(["case_manager", "witness"]);

  const upsert = useMutation({
    mutationFn: () =>
      api.admin.upsertGenieRoom({
        room_id: roomId,
        label,
        description,
        case_id: caseId,
        allowed_roles: roles,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "genie"] });
      setOpen(false);
    },
  });

  function toggleRole(r: RoleKey) {
    setRoles((prev) =>
      prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register Genie room</DialogTitle>
          <DialogDescription>
            Make a Genie space available to the agent and to users with the
            allowed roles.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium">Room ID</label>
              <Input
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                placeholder="genie_01abc…"
                className="font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Label</label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Customer billing data"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">Description</label>
            <Textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What kinds of questions this room can answer…"
            />
          </div>
          <div>
            <label className="text-xs font-medium">Case scope</label>
            <Select value={caseId} onValueChange={setCaseId}>
              <SelectTrigger>
                <SelectValue placeholder="Global (all cases)" />
              </SelectTrigger>
              <SelectContent>
                {cases.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium">Allowed roles</label>
            <div className="mt-1 flex flex-wrap gap-2 rounded-md border border-slate-200 bg-slate-50 p-2">
              {ALL_ROLES.map((r) => (
                <label
                  key={r}
                  className="flex items-center gap-1.5 text-xs text-slate-700"
                >
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 accent-brand-500"
                    checked={roles.includes(r)}
                    onChange={() => toggleRole(r)}
                  />
                  {r}
                </label>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!roomId || !label || upsert.isPending}
            onClick={() => upsert.mutate()}
          >
            Register
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
