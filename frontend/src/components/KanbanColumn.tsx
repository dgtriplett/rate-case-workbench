import { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface KanbanColumnProps {
  title: string;
  subtitle?: string;
  count?: number;
  accent?: "slate" | "brand" | "warning" | "info" | "danger";
  children: ReactNode;
}

const ACCENT_DOT: Record<string, string> = {
  slate: "bg-slate-400",
  brand: "bg-brand-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
  danger: "bg-rose-500",
};

export function KanbanColumn({
  title,
  subtitle,
  count,
  accent = "slate",
  children,
}: KanbanColumnProps) {
  return (
    <div className="flex w-72 shrink-0 flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/40 p-3">
      <div className="flex items-center justify-between pb-1.5">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", ACCENT_DOT[accent])} />
          <span className="text-sm font-semibold text-slate-700">{title}</span>
          {typeof count === "number" && (
            <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 ring-1 ring-slate-200">
              {count}
            </span>
          )}
        </div>
        {subtitle && (
          <span className="text-xs text-muted-foreground">{subtitle}</span>
        )}
      </div>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}
