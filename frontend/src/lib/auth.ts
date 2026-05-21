import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api";
import type { RoleKey, UserMeOut } from "./types";

const PERSONA_KEY = "rcw_view_as_persona";

export type Persona = "admin" | "case_manager" | "witness" | "reviewer" | "approver" | "viewer";

export function getStoredPersona(): Persona | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(PERSONA_KEY);
  return (v as Persona | null) || null;
}

export function setStoredPersona(p: Persona | null) {
  if (typeof window === "undefined") return;
  if (p) window.localStorage.setItem(PERSONA_KEY, p);
  else window.localStorage.removeItem(PERSONA_KEY);
  window.dispatchEvent(new CustomEvent("rcw-persona-changed"));
}

export function usePersonaOverride(): Persona | null {
  const [p, setP] = useState<Persona | null>(getStoredPersona());
  useEffect(() => {
    const h = () => setP(getStoredPersona());
    window.addEventListener("rcw-persona-changed", h);
    return () => window.removeEventListener("rcw-persona-changed", h);
  }, []);
  return p;
}

export function useCurrentUser() {
  return useQuery<UserMeOut>({
    queryKey: ["users", "me"],
    queryFn: () => api.me(),
    staleTime: 5 * 60_000,
  });
}

/** Returns the EFFECTIVE roles after applying any admin "view as" persona override. */
export function useEffectiveRoles(): RoleKey[] {
  const { data: me } = useCurrentUser();
  const override = usePersonaOverride();
  if (override && me?.roles?.includes("admin")) {
    return [override as RoleKey];
  }
  return (me?.roles ?? []) as RoleKey[];
}

export function useEffectiveIsAdmin(): boolean {
  const roles = useEffectiveRoles();
  return roles.includes("admin");
}

export function hasGlobalRole(
  user: UserMeOut | undefined,
  role: RoleKey,
): boolean {
  return !!user?.roles?.includes(role);
}

export function hasCaseRole(
  user: UserMeOut | undefined,
  caseId: string | undefined,
  role: RoleKey,
): boolean {
  if (!user || !caseId) return false;
  return !!user.case_roles?.[caseId]?.includes(role);
}

export function isAdmin(user: UserMeOut | undefined): boolean {
  return hasGlobalRole(user, "admin");
}

export function rolesForCase(
  user: UserMeOut | undefined,
  caseId: string | undefined,
): RoleKey[] {
  if (!user) return [];
  const global = user.roles ?? [];
  if (!caseId) return global;
  const cs = user.case_roles?.[caseId] ?? [];
  return Array.from(new Set([...global, ...cs])) as RoleKey[];
}

export function userInitials(displayName?: string | null, email?: string) {
  if (displayName) {
    const parts = displayName.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  if (email) return email.slice(0, 2).toUpperCase();
  return "??";
}
