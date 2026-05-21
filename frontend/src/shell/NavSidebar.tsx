import { Link, useLocation, useParams } from "@tanstack/react-router";
import {
  Activity,
  BookOpen,
  Briefcase,
  CalendarClock,
  CheckSquare,
  FileText,
  FolderTree,
  GanttChart,
  Gavel,
  GitCompare,
  Library,
  Home,
  Inbox,
  MessageSquare,
  ScrollText,
  Stamp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { rolesForCase, useCurrentUser } from "@/lib/auth";
import type { RoleKey } from "@/lib/types";

interface NavItem {
  label: string;
  to: string;
  icon: typeof Home;
  roles?: RoleKey[]; // if set, item shows only when user has one of these roles
  end?: boolean;
}

function buildNav(caseId: string): NavItem[] {
  return [
    { label: "Case home", to: `/cases/${caseId}`, icon: Home, end: true },
    { label: "Phase board", to: `/cases/${caseId}/board`, icon: GanttChart },
    { label: "Discovery", to: `/cases/${caseId}/discovery`, icon: Inbox },
    {
      label: "Review queue",
      to: `/cases/${caseId}/review`,
      icon: CheckSquare,
      roles: ["reviewer", "approver", "case_manager", "admin"],
    },
    { label: "Testimony & briefs", to: `/cases/${caseId}/testimony`, icon: ScrollText },
    {
      label: "Rebuttal",
      to: `/cases/${caseId}/rebuttal`,
      icon: MessageSquare,
    },
    { label: "Hearing prep", to: `/cases/${caseId}/hearing-prep`, icon: Gavel },
    { label: "Knowledge", to: `/cases/${caseId}/knowledge`, icon: BookOpen },
    { label: "Witnesses", to: `/cases/${caseId}/witnesses`, icon: Users },
    { label: "Calendar", to: `/cases/${caseId}/calendar`, icon: CalendarClock },
    { label: "Positions ledger", to: `/cases/${caseId}/positions-ledger`, icon: GitCompare },
    { label: "Cross-case insights", to: `/cases/${caseId}/cross-case`, icon: Library },
    {
      label: "Filing console",
      to: `/cases/${caseId}/filing`,
      icon: Gavel,
      roles: ["case_manager", "approver", "admin"],
    },
    { label: "Commission order", to: `/cases/${caseId}/order`, icon: Stamp },
    { label: "Compliance", to: `/cases/${caseId}/compliance`, icon: Stamp },
    { label: "Activity & audit", to: `/cases/${caseId}/activity`, icon: Activity },
  ];
}

export function NavSidebar() {
  const params = useParams({ strict: false }) as { caseId?: string };
  const loc = useLocation();
  const { data: me } = useCurrentUser();

  if (!params.caseId) return null;
  const items = buildNav(params.caseId);
  const userRoles = rolesForCase(me, params.caseId);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-white px-3 py-4">
      <nav className="flex-1 space-y-0.5">
        {items.map((item) => {
          if (item.roles && !item.roles.some((r) => userRoles.includes(r))) {
            return null;
          }
          const Icon = item.icon;
          const active = item.end
            ? loc.pathname === item.to
            : loc.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-all",
                active
                  ? "bg-brand-50 text-brand-800 shadow-soft"
                  : "hover:bg-slate-50 hover:text-slate-800",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4",
                  active ? "text-brand-700" : "text-slate-400 group-hover:text-slate-600",
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="rounded-lg border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3">
        <div className="mb-1 flex items-center gap-1.5">
          <FolderTree className="h-3.5 w-3.5 text-brand-600" />
          <span className="text-xs font-semibold tracking-tight text-slate-700">
            Your role
          </span>
        </div>
        <div className="text-xs text-muted-foreground">
          {userRoles.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {userRoles.map((r) => (
                <span
                  key={r}
                  className="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600 ring-1 ring-slate-200"
                >
                  {r.replace("_", " ")}
                </span>
              ))}
            </div>
          ) : (
            <span>No case role</span>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
        <FileText className="h-3 w-3" /> Workbench v1.0
      </div>
    </aside>
  );
}
