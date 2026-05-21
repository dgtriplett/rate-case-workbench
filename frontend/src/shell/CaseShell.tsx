import { Outlet, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { CaseContextProvider } from "@/lib/case-context";
import { NavSidebar } from "./NavSidebar";
import { Skeleton } from "@/components/ui/skeleton";

export default function CaseShell() {
  const { caseId } = useParams({ strict: false }) as { caseId: string };
  const { data, isLoading, isError } = useQuery({
    queryKey: ["cases", caseId],
    queryFn: () => api.getCase(caseId),
    enabled: !!caseId,
  });

  return (
    <CaseContextProvider caseId={caseId} caseData={data}>
      <div className="flex h-full w-full min-h-0">
        <NavSidebar />
        <section className="flex-1 min-w-0 overflow-y-auto">
          {isLoading && (
            <div className="space-y-3 p-6">
              <Skeleton className="h-8 w-1/3" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}
          {isError && (
            <div className="p-6 text-sm text-destructive">
              Failed to load case.
            </div>
          )}
          {data && <Outlet />}
        </section>
      </div>
    </CaseContextProvider>
  );
}
