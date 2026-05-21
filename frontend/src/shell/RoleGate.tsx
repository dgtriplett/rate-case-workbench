import { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { useCurrentUser, rolesForCase } from "@/lib/auth";
import type { RoleKey } from "@/lib/types";
import { EmptyState } from "@/components/ui/empty";

interface RoleGateProps {
  /** If true, requires global admin role */
  requireAdmin?: boolean;
  /** Must hold at least one of these roles (global or case-scoped) */
  anyOf?: RoleKey[];
  caseId?: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function RoleGate({
  requireAdmin,
  anyOf,
  caseId,
  fallback,
  children,
}: RoleGateProps) {
  const { data: me, isLoading } = useCurrentUser();

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  }

  if (requireAdmin) {
    if (!me?.roles?.includes("admin")) {
      return (
        fallback ?? (
          <div className="p-6">
            <EmptyState
              icon={<ShieldAlert className="h-5 w-5" />}
              title="Admin access required"
              description="You need the admin role to view this page. Ask a workspace admin to grant you access."
            />
          </div>
        )
      );
    }
    return <>{children}</>;
  }

  if (anyOf && anyOf.length > 0) {
    const roles = rolesForCase(me, caseId);
    const ok = anyOf.some((r) => roles.includes(r));
    if (!ok) {
      return (
        fallback ?? (
          <div className="p-6">
            <EmptyState
              icon={<ShieldAlert className="h-5 w-5" />}
              title="Not authorized"
              description={`Required role: ${anyOf.join(", ")}`}
            />
          </div>
        )
      );
    }
  }

  return <>{children}</>;
}
