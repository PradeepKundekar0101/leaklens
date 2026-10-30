"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiRequest } from "./api/http";

export interface ProcedureOption {
  code: string;
  name: string;
  icd10: string | null;
  category: string | null;
}

export interface ProviderOption {
  id: string;
  name: string;
  city: string;
  network: boolean;
}

export interface MemberPolicyOption {
  id: string;
  member_id: string;
  product_id: string;
  sum_insured: string;
  start_date: string;
  member_age: number | null;
  member_city: string | null;
}

/** Reference lists change rarely; keep them for the session. */
const REFERENCE = { staleTime: 30 * 60_000, gcTime: 60 * 60_000 } as const;

export function useProcedures() {
  return useQuery({
    queryKey: ["lookups", "procedures"],
    queryFn: () => apiRequest<{ items: ProcedureOption[] }>("/api/v1/lookups/procedures").then((r) => r.items),
    ...REFERENCE,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["lookups", "providers"],
    queryFn: () => apiRequest<{ items: ProviderOption[] }>("/api/v1/lookups/providers").then((r) => r.items),
    ...REFERENCE,
  });
}

/** Member policies whose policy or member ID starts with `q` (2+ characters). */
export function useMemberPolicySearch(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ["lookups", "member-policies", term.toUpperCase()],
    queryFn: () =>
      apiRequest<{ items: MemberPolicyOption[] }>("/api/v1/lookups/member-policies", { query: { q: term } }).then((r) => r.items),
    enabled: term.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}
