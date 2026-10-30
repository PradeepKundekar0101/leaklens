"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/errors";
import type { ClaimDetail } from "@/lib/api/types";
import { claimQueryKey } from "@/lib/claims";

export function useClaim(id: string) {
  return useQuery({
    queryKey: claimQueryKey(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/claims/{claim_id}", { params: { path: { claim_id: id } } })) as ClaimDetail,
    refetchInterval: (q) => {
      const c = q.state.data;
      if (!c) return false;
      if (c.status === "processing") return 2500;
      if (c.documents.some((d) => d.parse_status === "pending" || d.parse_status === "parsing")) return 2500;
      return false;
    },
  });
}
