import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/lib/auth";

/** Heartbeat-based presence indicator. Renders a small avatar stack of other
 *  users currently looking at this same artifact. */
export function PresenceIndicator({
  targetKind,
  targetId,
}: {
  targetKind: "testimony" | "response" | "brief";
  targetId: string;
}) {
  const qc = useQueryClient();
  const { data: me } = useCurrentUser();

  useEffect(() => {
    let cancelled = false;
    async function beat() {
      if (cancelled) return;
      try {
        await api.presenceHeartbeat({ target_kind: targetKind, target_id: targetId });
        qc.invalidateQueries({ queryKey: ["presence", targetKind, targetId] });
      } catch {
        // swallow — presence is best-effort
      }
    }
    beat();
    const t = setInterval(beat, 20_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [targetKind, targetId, qc]);

  const q = useQuery({
    queryKey: ["presence", targetKind, targetId],
    queryFn: () => api.presenceList(targetKind, targetId),
    refetchInterval: 25_000,
  });

  const viewers = (q.data?.viewers ?? []).filter((v: any) => v.user_id !== me?.id);
  if (viewers.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-900">
      <Users className="h-3 w-3" />
      <span>
        Also viewing: <strong>{viewers.map((v: any) => v.display_name || v.email).join(", ")}</strong>
      </span>
    </div>
  );
}
