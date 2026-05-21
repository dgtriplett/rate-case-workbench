import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Plus, UserPlus, Users as UsersIcon } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import type { RoleKey } from "@/lib/types";

interface UserRow {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  roles: RoleKey[];
  case_roles?: Record<string, RoleKey[]>;
}

const ALL_ROLES: RoleKey[] = [
  "admin",
  "case_manager",
  "reviewer",
  "approver",
  "witness",
  "viewer",
];

export default function AdminUsers() {
  const usersQ = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.admin.listUsers() as Promise<UserRow[]>,
  });
  const casesQ = useQuery({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
  });

  const users = usersQ.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow={<>Admin</>}
        title="Users & roles"
        description="Invite users, grant global or case-scoped roles, and manage witness profiles."
        actions={
          <InviteDialog cases={casesQ.data ?? []}>
            <Button>
              <UserPlus className="h-3.5 w-3.5" />
              Invite user
            </Button>
          </InviteDialog>
        }
      />

      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-white">
          {usersQ.isLoading ? (
            <Skeleton className="h-64" />
          ) : users.length === 0 ? (
            <EmptyState
              icon={<UsersIcon className="h-4 w-4" />}
              title="No users yet."
              description="Users are auto-provisioned on first SSO login. You can also pre-invite users below."
              action={
                <InviteDialog cases={casesQ.data ?? []}>
                  <Button>
                    <UserPlus className="h-3.5 w-3.5" />
                    Invite user
                  </Button>
                </InviteDialog>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead className="w-64">Global roles</TableHead>
                  <TableHead className="w-64">Case roles</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-50 text-[10px] font-semibold text-brand-700">
                          {(u.display_name || u.email).slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-slate-800">
                            {u.display_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {u.email}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {(u.roles ?? []).map((r) => (
                          <Badge key={r} variant="brand">
                            {r}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(u.case_roles ?? {})
                          .slice(0, 4)
                          .map(([caseId, roles]) => (
                            <Badge key={caseId} variant="outline">
                              {caseId.slice(0, 6)} · {roles.join(",")}
                            </Badge>
                          ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      {u.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="slate">Inactive</Badge>
                      )}
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

function InviteDialog({
  children,
  cases,
}: {
  children: React.ReactNode;
  cases: { id: string; name: string }[];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<RoleKey>("viewer");
  const [caseId, setCaseId] = useState<string | undefined>();

  const inviteMut = useMutation({
    mutationFn: () =>
      api.admin.inviteUser({
        email,
        display_name: displayName,
        roles: [role],
        case_id: caseId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      setOpen(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite user</DialogTitle>
          <DialogDescription>
            Grant a user a global or case-scoped role. They will be activated
            when they next log in.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium">Email</label>
            <Input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
            />
          </div>
          <div>
            <label className="text-xs font-medium">Display name</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium">Role</label>
              <Select value={role} onValueChange={(v) => setRole(v as RoleKey)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium">
                Scope (optional case)
              </label>
              <Select value={caseId} onValueChange={setCaseId}>
                <SelectTrigger>
                  <SelectValue placeholder="Global" />
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
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => inviteMut.mutate()}
            disabled={!email || !displayName || inviteMut.isPending}
          >
            <Plus className="h-3.5 w-3.5" /> Invite
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
