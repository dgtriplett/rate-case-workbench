import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { FeatureFlagOut } from "./types";

export function useFeatureFlags() {
  return useQuery<FeatureFlagOut[]>({
    queryKey: ["admin", "feature-flags"],
    queryFn: () => api.admin.listFeatureFlags(),
    staleTime: 60_000,
  });
}

export function useFeatureFlag(key: string): boolean {
  const { data } = useFeatureFlags();
  const flag = data?.find((f) => f.key === key);
  // Default to enabled if not present so missing flags don't accidentally hide UI
  return flag ? flag.enabled : true;
}
