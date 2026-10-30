"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "./api/client";
import { unwrap } from "./api/errors";

export const claimsQueryKey = ["claims"] as const;
export const claimQueryKey = (id: string) => ["claim", id] as const;

/** Starts the pipeline for one claim and returns the job id. */
export function useProcessClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (claimId: string) => {
      const data = unwrap(
        await api.POST("/api/v1/claims/{claim_id}/process", { params: { path: { claim_id: claimId } } }),
      ) as { job_id: number };
      return data.job_id;
    },
    onSuccess: (_jobId, claimId) => {
      void queryClient.invalidateQueries({ queryKey: claimsQueryKey });
      void queryClient.invalidateQueries({ queryKey: claimQueryKey(claimId) });
    },
  });
}
