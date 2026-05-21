import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Bell, CheckCircle2, FileSearch, GavelIcon, Inbox, Timer } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/cn";

type Notif = {
  id: string;
  kind:
    | "assigned_dr"
    | "review_pending"
    | "approval_pending"
    | "filing_pending"
    | "due_soon";
  title: string;
  detail: string;
  case_id: string | null;
  target_kind: string;
  target_id: string;
  severity: "info" | "warning" | "urgent";
  timestamp: string | null;
};

const ICON: Record<Notif["kind"], React.ComponentType<{ className?: string }>> = {
  assigned_dr: Inbox,
  review_pending: FileSearch,
  approval_pending: GavelIcon,
  filing_pending: CheckCircle2,
  due_soon: Timer,
};

const SEV_BG: Record<Notif["severity"], string> = {
  info: "bg-slate-100 text-slate-600",
  warning: "bg-amber-100 text-amber-700",
  urgent: "bg-rose-100 text-rose-700",
};

const KIND_LABEL: Record<Notif["kind"], string> = {
  assigned_dr: "Assigned to me",
  review_pending: "Pending review",
  approval_pending: "Pending approval",
  filing_pending: "Ready to file",
  due_soon: "Due soon",
};

function targetLink(n: Notif): string {
  if (n.target_kind === "data_request" && n.case_id) {
    return `/cases/${n.case_id}/discovery/${n.target_id}`;
  }
  if (n.target_kind === "response" && n.case_id) {
    if (n.kind === "filing_pending") return `/cases/${n.case_id}/filing`;
    return `/cases/${n.case_id}/review`;
  }
  return n.case_id ? `/cases/${n.case_id}` : "/";
}

export function NotificationsBell() {
  const q = useQuery<Notif[]>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const r = await fetch("/api/v1/notifications");
      if (!r.ok) throw new Error("failed");
      return r.json();
    },
    refetchInterval: 30_000,
  });

  const items = q.data ?? [];
  const urgent = items.filter((i) => i.severity === "urgent").length;
  const totalDot = items.length > 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-white text-slate-600 hover:bg-slate-50">
          <Bell className="h-4 w-4" />
          {totalDot && (
            <span
              className={cn(
                "absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-semibold ring-2 ring-white",
                urgent ? "bg-rose-500 text-white" : "bg-brand-500 text-white",
              )}
            >
              {items.length > 99 ? "99+" : items.length}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[400px] p-0">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
          <div>
            <div className="text-sm font-semibold text-slate-900">Notifications</div>
            <div className="text-[11px] text-slate-500">
              {items.length} item{items.length === 1 ? "" : "s"} need your attention
            </div>
          </div>
        </div>
        <div className="max-h-[480px] overflow-y-auto">
          {q.isLoading ? (
            <div className="p-6 text-center text-xs text-slate-500">Loading…</div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-8 text-center">
              <CheckCircle2 className="h-7 w-7 text-emerald-500" />
              <div className="text-sm font-medium text-slate-700">All caught up</div>
              <div className="text-[11px] text-slate-500">
                No pending DRs, reviews, approvals, or deadlines.
              </div>
            </div>
          ) : (
            items.map((n) => {
              const Icon = ICON[n.kind];
              return (
                <Link
                  key={n.id}
                  to={targetLink(n)}
                  className="flex gap-3 border-b border-slate-100 px-4 py-3 hover:bg-slate-50 last:border-0"
                >
                  <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full", SEV_BG[n.severity])}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-slate-800">
                        {n.title}
                      </span>
                      <span className="text-[10px] uppercase tracking-wide text-slate-400">
                        {KIND_LABEL[n.kind]}
                      </span>
                    </div>
                    <div className="line-clamp-2 text-[11px] text-slate-500">
                      {n.detail}
                    </div>
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
