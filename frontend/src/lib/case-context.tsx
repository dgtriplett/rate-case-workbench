import { createContext, ReactNode, useContext } from "react";
import type { CaseOut } from "./types";

interface CaseContextValue {
  caseId: string;
  caseData: CaseOut | undefined;
}

const CaseContext = createContext<CaseContextValue | null>(null);

export function CaseContextProvider({
  caseId,
  caseData,
  children,
}: {
  caseId: string;
  caseData: CaseOut | undefined;
  children: ReactNode;
}) {
  return (
    <CaseContext.Provider value={{ caseId, caseData }}>
      {children}
    </CaseContext.Provider>
  );
}

export function useCaseContext(): CaseContextValue {
  const ctx = useContext(CaseContext);
  if (!ctx)
    throw new Error("useCaseContext must be used inside CaseContextProvider");
  return ctx;
}

/** Like useCaseContext but returns null instead of throwing when no provider is mounted. */
export function useOptionalCaseContext(): CaseContextValue | null {
  return useContext(CaseContext);
}
