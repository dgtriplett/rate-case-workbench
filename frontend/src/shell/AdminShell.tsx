import { Link, Outlet, useLocation } from "@tanstack/react-router";
import {
  AlignJustify,
  Banknote,
  Brain,
  Database,
  Flag,
  History,
  Layers,
  MessagesSquare,
  Plug,
  Settings,
  Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { RoleGate } from "./RoleGate";

const tabs = [
  { label: "Cases", to: "/admin/cases", icon: Layers },
  { label: "Phase templates", to: "/admin/phase-templates", icon: AlignJustify },
  { label: "Users", to: "/admin/users", icon: Users },
  { label: "Models", to: "/admin/models", icon: Brain },
  { label: "Knowledge sources", to: "/admin/knowledge-sources", icon: Database },
  { label: "Genie", to: "/admin/genie", icon: MessagesSquare },
  { label: "Feature flags", to: "/admin/feature-flags", icon: Flag },
  { label: "Integrations", to: "/admin/integrations", icon: Plug },
  { label: "Audit", to: "/admin/audit", icon: History },
];

export default function AdminShell() {
  const loc = useLocation();
  return (
    <RoleGate requireAdmin>
      <div className="flex h-full w-full min-h-0">
        <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-white px-3 py-4">
          <div className="mb-3 flex items-center gap-2 px-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-white">
              <Settings className="h-3.5 w-3.5" />
            </div>
            <div>
              <div className="text-sm font-semibold">Admin portal</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Global configuration
              </div>
            </div>
          </div>
          <nav className="space-y-0.5">
            {tabs.map((t) => {
              const Icon = t.icon;
              const active =
                loc.pathname === t.to ||
                (t.to === "/admin/cases" && loc.pathname === "/admin");
              return (
                <Link
                  key={t.to}
                  to={t.to}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-all",
                    active
                      ? "bg-slate-900 text-white shadow-soft"
                      : "hover:bg-slate-50 hover:text-slate-800",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4",
                      active ? "text-white" : "text-slate-400",
                    )}
                  />
                  {t.label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-1 flex items-center gap-1.5">
              <Banknote className="h-3.5 w-3.5 text-slate-500" />
              <span className="text-xs font-semibold text-slate-700">
                Spend
              </span>
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Model and retrieval spend is reported on the Audit page.
            </p>
          </div>
        </aside>
        <section className="flex-1 min-w-0 overflow-y-auto">
          <Outlet />
        </section>
      </div>
    </RoleGate>
  );
}
