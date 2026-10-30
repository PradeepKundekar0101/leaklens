"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { apiRequest } from "./api/http";
import type { Job } from "./api/types";

export const jobQueryKey = (id: number) => ["jobs", id] as const;

export function isJobFinished(job: Pick<Job, "status"> | undefined): boolean {
  return job?.status === "done" || job?.status === "failed";
}

/**
 * Polls a background job until it finishes. `onFinish` fires once with the final job.
 */
export function useJob(jobId: number | null | undefined, { onFinish, interval = 1500 }: {
  onFinish?: (job: Job) => void;
  interval?: number;
} = {}) {
  const query = useQuery({
    queryKey: jobQueryKey(jobId ?? 0),
    queryFn: () => apiRequest<Job>(`/api/v1/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => (isJobFinished(q.state.data) ? false : interval),
  });

  const notified = useRef<number | null>(null);
  const onFinishRef = useRef(onFinish);
  useEffect(() => {
    onFinishRef.current = onFinish;
  });
  useEffect(() => {
    const job = query.data;
    if (job && isJobFinished(job) && notified.current !== job.id) {
      notified.current = job.id;
      onFinishRef.current?.(job);
    }
  }, [query.data]);

  return query;
}
