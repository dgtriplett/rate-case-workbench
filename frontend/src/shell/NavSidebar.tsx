import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "@tanstack/react-router";
import {
  Activity,
  ArrowRightFromLine,
  BookOpen,
  CalendarClock,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  FileSignature,
  FileText,
  FolderTree,
  GanttChart,
  Gavel,
  GitCompare,
  Handshake,
  Home,
  Inbox,
  Library,
  Megaphone,
  MessageCircle,
  MessageSquare,
  Scale,
  ScrollText,
  Stamp,
  UserSquare,
  Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useCurrentUser, useEffectiveRoles } from "@/lib/auth";
import type { RoleKey } from "@/lib/types";

interface NavItem {
  label: string;
  to: string;
  icon: typeof Home;
  roles?: RoleKey[]; // shown when effective role intersects
  end?: boolean;
}

interface NavGroup {
  id: string;
  label: string;
  stage?: string; // process stage number/letter
  items: NavItem[];
}

function buildGroups(caseId: string): NavGroup[] {
  return [
    // ── Always-on cross-cutting ──
    {
      id: "overview",
      label: "Overview",
      items: [
        { label: "Case home", to: `/cases/${caseId}`, icon: Home, end: true },
        { label: "Phase board", to: `/cases/${caseId}/board`, icon: GanttChart },
        { label: "Calendar", to: `/cases/${caseId}/calendar`, icon: CalendarClock },
        { label: "Positions ledger", to: `/cases/${caseId}/positions-ledger`, icon: GitCompare },
        { label: "Cross-case insights", to: `/cases/${caseId}/cross-case`, icon: Library },
      ],
    },
    // ── Stage 1 — Prepare for filing ──
    {
      id: "prepare",
      label: "1. Prepare for filing",
      stage: "1",
      items: [
        { label: "Application workbench", to: `/cases/${caseId}/application-workbench`, icon: FileSignature, roles: ["case_manager", "approver", "admin"] },
        { label: "Witnesses", to: `/cases/${caseId}/witnesses`, icon: Users, roles: ["case_manager", "witness", "admin"] },
        { label: "Knowledge library", to: `/cases/${caseId}/knowledge`, icon: BookOpen },
      ],
    },
    // ── Stage 2 — Engage public ──
    {
      id: "engage",
      label: "2. Engage public",
      stage: "2",
      items: [
        { label: "Public notice", to: `/cases/${caseId}/public-notice`, icon: Megaphone, roles: ["case_manager", "approver", "admin"] },
        { label: "Stakeholders", to: `/cases/${caseId}/stakeholders`, icon: Users, roles: ["case_manager", "approver", "admin"] },
        { label: "Public comments", to: `/cases/${caseId}/public-comments`, icon: MessageCircle, roles: ["case_manager", "reviewer", "approver", "admin"] },
      ],
    },
    // ── Stage 3 — Discover & analyze ──
    {
      id: "discover",
      label: "3. Discover & analyze",
      stage: "3",
      items: [
        { label: "Discovery (inbound)", to: `/cases/${caseId}/discovery`, icon: Inbox },
        { label: "Outbound DRs", to: `/cases/${caseId}/discovery-outbound`, icon: ArrowRightFromLine, roles: ["case_manager", "witness", "approver", "admin"] },
        { label: "Review queue", to: `/cases/${caseId}/review`, icon: CheckSquare, roles: ["reviewer", "approver", "case_manager", "admin"] },
        { label: "Intervenor testimony", to: `/cases/${caseId}/intervenor-testimony`, icon: UserSquare, roles: ["case_manager", "witness", "reviewer", "admin"] },
      ],
    },
    // ── Stage 4 — Draft & file ──
    {
      id: "draft",
      label: "4. Draft & file",
      stage: "4",
      items: [
        { label: "Testimony & briefs", to: `/cases/${caseId}/testimony`, icon: ScrollText, roles: ["case_manager", "witness", "reviewer", "approver", "admin"] },
        { label: "Rebuttal", to: `/cases/${caseId}/rebuttal`, icon: MessageSquare, roles: ["case_manager", "witness", "reviewer", "admin"] },
        { label: "Filing console", to: `/cases/${caseId}/filing`, icon: Gavel, roles: ["case_manager", "approver", "admin"] },
      ],
    },
    // ── Stage 5 — Negotiate & hearings ──
    {
      id: "negotiate",
      label: "5. Negotiate & hearings",
      stage: "5",
      items: [
        { label: "Settlements", to: `/cases/${caseId}/settlements`, icon: Handshake, roles: ["case_manager", "reviewer", "approver", "admin"] },
        { label: "Hearing prep", to: `/cases/${caseId}/hearing-prep`, icon: Gavel, roles: ["case_manager", "witness", "reviewer", "admin"] },
      ],
    },
    // ── Stage 6 — Decision & comply ──
    {
      id: "decide",
      label: "6. Decision & comply",
      stage: "6",
      items: [
        { label: "ALJ recommendation", to: `/cases/${caseId}/alj-recommendation`, icon: Scale, roles: ["case_manager", "reviewer", "approver", "admin"] },
        { label: "Commission order", to: `/cases/${caseId}/order`, icon: Stamp },
        { label: "Compliance", to: `/cases/${caseId}/compliance`, icon: Stamp, roles: ["case_manager", "reviewer", "approver", "admin"] },
      ],
    },
    // ── Audit (admin/reviewer mainly) ──
    {
      id: "audit",
      label: "Audit",
      items: [
        { label: "Activity & audit", to: `/cases/${caseId}/activity`, icon: Activity, roles: ["case_manager", "reviewer", "approver", "admin"] },
      ],
    },
  ];
}

function activeGroupId(pathname: string, groups: NavGroup[]): string | undefined {
  for (const g of groups) {
    for (const it of g.items) {
      if (!it.end && pathname.startsWith(it.to)) return g.id;
      if (it.end && pathname === it.to) return g.id;
    }
  }
  return undefined;
}

export function NavSidebar() {
  const params = useParams({ strict: false }) as { caseId?: string };
  const loc = useLocation();
  const { data: me } = useCurrentUser();
  const effective = useEffectiveRoles();

  // Admin (without persona override) sees everything regardless of role gates.
  const showAll = effective.includes("admin");

  const groups = useMemo(
    () => (params.caseId ? buildGroups(params.caseId) : []),
    [params.caseId],
  );

  const visibleGroups = useMemo(() => {
    return groups
      .map((g) => ({
        ...g,
        items: g.items.filter((it) => !it.roles || showAll || it.roles.some((r) => effective.includes(r))),
      }))
      .filter((g) => g.items.length > 0);
  }, [groups, effective, showAll]);

  const [open, setOpen] = useState<Record<string, boolean>>({});
  // Default all groups open on first render — collapsing is a user gesture.
  useEffect(() => {
    setOpen((prev) => {
      const next = { ...prev };
      for (const g of visibleGroups) {
        if (next[g.id] === undefined) next[g.id] = true;
      }
      return next;
    });
  }, [visibleGroups]);

  // Whenever the user navigates somewhere, ensure that section is open.
  useEffect(() => {
    const id = activeGroupId(loc.pathname, visibleGroups);
    if (id) setOpen((prev) => ({ ...prev, [id]: true }));
  }, [loc.pathname, visibleGroups]);

  if (!params.caseId) return null;
  const activeId = activeGroupId(loc.pathname, visibleGroups);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-white px-3 py-3">
      <nav className="flex-1 space-y-2 overflow-y-auto pr-1">
        {visibleGroups.map((g) => {
          const isOpen = open[g.id] ?? true;
          const isActiveGroup = activeId === g.id;
          return (
            <div key={g.id}>
              <button
                onClick={() => setOpen((p) => ({ ...p, [g.id]: !isOpen }))}
                className={cn(
                  "flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors",
                  isActiveGroup ? "text-brand-700" : "text-slate-500 hover:text-slate-700",
                )}
              >
                {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                {g.stage && (
                  <span className={cn(
                    "flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold",
                    isActiveGroup ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-700",
                  )}>{g.stage}</span>
                )}
                <span>{g.label}</span>
              </button>
              {isOpen && (
                <div className="mt-0.5 space-y-0.5 border-l border-slate-100 pl-2">
                  {g.items.map((item) => {
                    const Icon = item.icon;
                    const active = item.end ? loc.pathname === item.to : loc.pathname.startsWith(item.to);
                    return (
                      <Link
                        key={item.to}
                        to={item.to}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm font-medium text-slate-600 transition-all",
                          active
                            ? "bg-brand-50 text-brand-800 shadow-soft"
                            : "hover:bg-slate-50 hover:text-slate-800",
                        )}
                      >
                        <Icon className={cn("h-3.5 w-3.5", active ? "text-brand-700" : "text-slate-400 group-hover:text-slate-600")} />
                        <span className="leading-tight">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="mt-2 space-y-2">
        <div className="rounded-lg border border-slate-200 bg-gradient-to-br from-slate-50 to-white px-2.5 py-2">
          <div className="flex items-center gap-1.5">
            <FolderTree className="h-3 w-3 text-brand-600" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700">View</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {effective.length > 0 ? (
              effective.map((r) => (
                <span
                  key={r}
                  className="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600 ring-1 ring-slate-200"
                >
                  {r.replace("_", " ")}
                </span>
              ))
            ) : (
              <span className="text-[10px] text-muted-foreground">No case role</span>
            )}
          </div>
          {showAll && (
            <div className="mt-1 text-[10px] text-amber-700">Admin · all modules visible</div>
          )}
        </div>
        <div className="flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
          <FileText className="h-3 w-3" /> Workbench v1.0
        </div>
      </div>
    </aside>
  );
}
