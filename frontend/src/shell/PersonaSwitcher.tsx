import { Eye } from "lucide-react";
import {
  Persona,
  setStoredPersona,
  useCurrentUser,
  usePersonaOverride,
} from "@/lib/auth";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PERSONAS: { value: Persona; label: string; description: string }[] = [
  { value: "admin", label: "Admin (default)", description: "Your real role — full access" },
  { value: "case_manager", label: "View as Case Manager", description: "Sees workflow + assignments" },
  { value: "witness", label: "View as Witness / SME", description: "Sees only their assigned DRs" },
  { value: "reviewer", label: "View as Reviewer", description: "Sees Review Queue + consistency" },
  { value: "approver", label: "View as Approver", description: "Sees approval + Filing Console" },
  { value: "viewer", label: "View as Viewer", description: "Read-only across the app" },
];

export function PersonaSwitcher() {
  const { data: me } = useCurrentUser();
  const current = usePersonaOverride();
  const isAdmin = !!me?.roles?.includes("admin");
  if (!isAdmin) return null;

  const value: Persona = (current as Persona | null) ?? "admin";

  return (
    <Select
      value={value}
      onValueChange={(v) => setStoredPersona(v === "admin" ? null : (v as Persona))}
    >
      <SelectTrigger className="h-8 w-[210px] rounded-md border-amber-300 bg-amber-50 text-xs text-amber-900 hover:bg-amber-100">
        <div className="flex items-center gap-1.5 truncate">
          <Eye className="h-3.5 w-3.5" />
          <SelectValue placeholder="View as…" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {PERSONAS.map((p) => (
          <SelectItem key={p.value} value={p.value}>
            <div className="flex flex-col">
              <span className="text-sm font-medium">{p.label}</span>
              <span className="text-[11px] text-slate-500">{p.description}</span>
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
