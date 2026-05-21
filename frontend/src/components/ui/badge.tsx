import { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tracking-tight border",
  {
    variants: {
      variant: {
        default:
          "bg-slate-50 text-slate-700 border-slate-200",
        brand:
          "bg-brand-50 text-brand-700 border-brand-200",
        info: "bg-sky-50 text-sky-700 border-sky-200",
        warning: "bg-amber-50 text-amber-700 border-amber-200",
        danger: "bg-rose-50 text-rose-700 border-rose-200",
        success: "bg-emerald-50 text-emerald-700 border-emerald-200",
        violet: "bg-violet-50 text-violet-700 border-violet-200",
        slate: "bg-slate-100 text-slate-700 border-slate-200",
        outline: "bg-transparent border-border text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { badgeVariants };
