"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Cog, User } from "lucide-react";

import { AuditPayload } from "@/components/audit-payload";
import { Panel } from "@/components/page";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { AuditEntry } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { humanize } from "@/lib/labels";

const ICONS = { user: User, agent: Bot, system: Cog } as const;

export function AuditTab({ claimId, status }: { claimId: string; status: string }) {
  const audit = useQuery({
    queryKey: ["claim-audit", claimId, status],
    queryFn: () => apiRequest<{ items: AuditEntry[]; total: number }>(`/api/v1/claims/${encodeURIComponent(claimId)}/audit`),
  });

  return (
    <Panel>
      {audit.isPending ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : audit.isError ? (
        <p className="px-4 py-8 text-center text-[13px] text-destructive">{getErrorMessage(audit.error)}</p>
      ) : audit.data.items.length === 0 ? (
        <p className="px-4 py-8 text-center text-[13px] text-muted-foreground">No activity recorded for this claim yet.</p>
      ) : (
        <ol className="relative px-4 py-3">
          {audit.data.items.map((e, i) => {
            const Icon = ICONS[e.actor_type as keyof typeof ICONS] ?? Cog;
            const last = i === audit.data.items.length - 1;
            return (
              <li key={e.id} className="relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-3 pb-4 last:pb-1">
                {!last && <span className="absolute top-7 bottom-0 left-[0.8125rem] w-px bg-border" aria-hidden="true" />}
                <span className="z-10 flex size-7 items-center justify-center rounded-full border bg-card text-muted-foreground">
                  <Icon className="size-3.5" aria-hidden="true" />
                </span>
                <div className="min-w-0 pt-0.5">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <p className="text-[13px]">
                      <span className="font-semibold">{humanize(e.action)}</span>
                      <span className="text-muted-foreground"> by {e.actor_name ?? e.actor_id}</span>
                      {e.model && <span className="ml-1.5 text-xs text-muted-foreground">{e.model}</span>}
                    </p>
                    <time className="num text-xs text-muted-foreground" dateTime={e.created_at}>
                      {formatDateTime(e.created_at)}
                    </time>
                  </div>
                  <AuditPayload payload={e.payload} />
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
