"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, X } from "lucide-react";
import Link from "next/link";

import { AuditPayload } from "@/components/audit-payload";
import { FilterSelect, Pagination, TableStateRows } from "@/components/data-table";
import { PageHeader, Panel } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest, withQuery } from "@/lib/api/http";
import type { AuditEntry } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { humanize } from "@/lib/labels";
import { useSyncedState, useUrlState } from "@/lib/use-url-state";
import { cn } from "@/lib/utils";

const DEFAULTS = {
  page: "1",
  page_size: "50",
  entity: "",
  entity_id: "",
  actor_type: "",
  actor_id: "",
  action: "",
  date_from: "",
  date_to: "",
};
const FILTER_KEYS = ["entity", "entity_id", "actor_type", "actor_id", "action", "date_from", "date_to"] as const;

const ENTITY_OPTIONS = ["claim", "policy", "job", "user"].map((v) => ({ value: v, label: humanize(v) }));
const ACTOR_OPTIONS = ["user", "agent", "system"].map((v) => ({ value: v, label: humanize(v) }));

export function AuditLog() {
  const [state, update] = useUrlState(DEFAULTS);
  const page = Math.max(1, Number(state.page) || 1);
  const pageSize = Number(state.page_size) || 50;
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, state[k]]));
  const datesBad = state.date_from && state.date_to && state.date_to < state.date_from;

  const audit = useQuery({
    queryKey: ["audit", state],
    queryFn: () =>
      apiRequest<{ items: AuditEntry[]; total: number; actions: string[] }>("/api/v1/audit", {
        query: { ...filters, page, page_size: pageSize },
      }),
    placeholderData: keepPreviousData,
    enabled: !datesBad,
  });
  const actions = audit.data?.actions ?? [];
  const items = audit.data?.items ?? [];
  const active = FILTER_KEYS.some((k) => state[k]);

  return (
    <>
      <PageHeader
        title="Audit"
        description="Every review decision, agent run, parameter approval and retraining, newest first."
        actions={
          <Button asChild variant="outline" className="bg-card">
            <a href={withQuery("/api/v1/audit/export", filters)} download>
              <Download data-icon="inline-start" aria-hidden="true" />
              Export CSV
            </a>
          </Button>
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <FilterSelect label="Entity" value={state.entity} onChange={(v) => update({ entity: v, page: "1" })} options={ENTITY_OPTIONS} />
        <TextFilter label="Entity ID" value={state.entity_id} onChange={(v) => update({ entity_id: v, page: "1" })} />
        <FilterSelect label="Actor" value={state.actor_type} onChange={(v) => update({ actor_type: v, page: "1" })} options={ACTOR_OPTIONS} />
        <TextFilter label="Actor ID" value={state.actor_id} onChange={(v) => update({ actor_id: v, page: "1" })} className="w-28" />
        <FilterSelect
          label="Action"
          value={state.action}
          onChange={(v) => update({ action: v, page: "1" })}
          options={actions.map((a) => ({ value: a, label: humanize(a) }))}
        />
        <label className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
          From
          <Input type="date" value={state.date_from} onChange={(e) => update({ date_from: e.target.value, page: "1" })} className="num h-7 w-36 bg-card text-[13px]" />
        </label>
        <label className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
          To
          <Input
            type="date"
            value={state.date_to}
            min={state.date_from || undefined}
            onChange={(e) => update({ date_to: e.target.value, page: "1" })}
            aria-invalid={!!datesBad}
            className="num h-7 w-36 bg-card text-[13px]"
          />
        </label>
        {active && (
          <Button variant="ghost" size="sm" onClick={() => update({ ...Object.fromEntries(FILTER_KEYS.map((k) => [k, ""])), page: "1" })}>
            <X data-icon="inline-start" aria-hidden="true" />
            Clear filters
          </Button>
        )}
      </div>
      {datesBad && <p className="mb-3 text-[13px] text-destructive">The end date is before the start date.</p>}

      <Panel className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40">Time</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className={cn(audit.isFetching && audit.isPlaceholderData && "opacity-60")}>
            <TableStateRows
              colSpan={5}
              isLoading={audit.isPending && !datesBad}
              error={audit.isError ? getErrorMessage(audit.error) : null}
              onRetry={() => audit.refetch()}
              isEmpty={items.length === 0}
              emptyTitle={active ? "No entries match these filters" : "No audit entries yet"}
            />
            {items.map((e) => (
              <TableRow key={e.id} className="align-top">
                <TableCell className="num text-muted-foreground">{formatDateTime(e.created_at)}</TableCell>
                <TableCell>
                  <div className="font-medium">{e.actor_name ?? e.actor_id}</div>
                  <div className="text-xs text-muted-foreground">{humanize(e.actor_type)}</div>
                </TableCell>
                <TableCell>
                  <div className="font-medium">{humanize(e.action)}</div>
                  {e.model && <div className="text-xs text-muted-foreground">{e.model}</div>}
                </TableCell>
                <TableCell>
                  {e.entity === "claim" ? (
                    <Link href={`/claims/${encodeURIComponent(e.entity_id)}`} className="num font-medium text-primary hover:underline">
                      {e.entity_id}
                    </Link>
                  ) : (
                    <span className="num">{e.entity_id}</span>
                  )}
                  <div className="text-xs text-muted-foreground">{humanize(e.entity)}</div>
                </TableCell>
                <TableCell className="max-w-[32rem] whitespace-normal">
                  <AuditPayload payload={e.payload} max={6} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={pageSize}
          total={audit.data?.total}
          isFetching={audit.isFetching}
          onPage={(p) => update({ page: String(p) })}
          onPageSize={(s) => update({ page_size: String(s), page: "1" })}
        />
      </Panel>
    </>
  );
}

function TextFilter({ label, value, onChange, className }: { label: string; value: string; onChange: (v: string) => void; className?: string }) {
  const [draft, setDraft] = useSyncedState(value);
  const commit = () => draft.trim() !== value && onChange(draft.trim());
  return (
    <Input
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => e.key === "Enter" && commit()}
      placeholder={label}
      aria-label={label}
      className={cn("h-7 w-36 bg-card text-[13px]", value && "border-primary/50", className)}
    />
  );
}
