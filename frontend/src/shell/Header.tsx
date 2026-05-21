import { Link } from "@tanstack/react-router";
import { Briefcase, Sparkles } from "lucide-react";
import { CaseSwitcher } from "./CaseSwitcher";
import { PersonaSwitcher } from "./PersonaSwitcher";
import {
  useCurrentUser,
  userInitials,
  useEffectiveRoles,
  usePersonaOverride,
} from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { NotificationsBell } from "@/components/NotificationsBell";

export function Header() {
  const { data: me } = useCurrentUser();
  const isAdmin = me?.roles?.includes("admin");
  const effectiveRoles = useEffectiveRoles();
  const override = usePersonaOverride();
  const showAdminLink = !!isAdmin && (!override || effectiveRoles.includes("admin"));

  // Always render the email as the primary identity. Display name is shown as a
  // small subtitle when it differs from the email's local-part.
  const email = me?.email ?? "";
  const localPart = email.split("@")[0] ?? "";
  const showDisplayName =
    !!me?.display_name && me.display_name.toLowerCase() !== localPart.toLowerCase();

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-white/85 px-5 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <Link to="/" className="group flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-soft transition-transform group-hover:scale-105">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight">
              Rate Case Workbench
            </span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Utility regulatory operations
            </span>
          </div>
        </Link>
        <span className="mx-2 h-6 w-px bg-border" />
        <CaseSwitcher />
      </div>

      <div className="flex items-center gap-2">
        <Link
          to="/portfolio"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <Briefcase className="h-3.5 w-3.5" />
          Portfolio
        </Link>
        {isAdmin && <PersonaSwitcher />}

        {showAdminLink && (
          <Link
            to="/admin/cases"
            className="rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Admin
          </Link>
        )}

        <NotificationsBell />

        <div className="flex items-center gap-2 rounded-md border border-border bg-white px-2.5 py-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-50 text-[11px] font-semibold text-brand-700">
            {userInitials(me?.display_name, email)}
          </div>
          <div className="hidden flex-col leading-tight md:flex">
            <span className="text-xs font-medium text-slate-800">
              {email || "Loading…"}
            </span>
            {showDisplayName && (
              <span className="text-[10px] text-muted-foreground">
                {me?.display_name}
              </span>
            )}
          </div>
          {effectiveRoles.length > 0 && (
            <Badge variant="outline" className="hidden lg:inline-flex">
              {override && override !== "admin" ? `viewing as ${override}` : effectiveRoles[0]}
            </Badge>
          )}
        </div>
      </div>
    </header>
  );
}
