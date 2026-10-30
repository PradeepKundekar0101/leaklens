"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play, Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ClaimStatusPill } from "@/components/claim-status";
import { Combobox } from "@/components/combobox";
import { FilterSelect, Pagination, SortableHead, TableStateRows } from "@/components/data-table";
import { PageHeader, Panel } from "@/components/page";
import { ACTION_META, ACTIONS, ActionBadge, isClaimAction, isRiskLevel, RiskBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api/client";
import { getErrorMessage, unwrap } from "@/lib/api/errors";
import type { ClaimListItem, Page } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { hasRole } from "@/lib/auth/roles";
import { claimsQueryKey, useProcessClaim } from "@/lib/claims";
import { formatDate, formatINR } from "@/lib/format";
import { useJob } from "@/lib/jobs";
import { useProviders } from "@/lib/lookups";
import { CLAIM_STATUS_META, CLAIM_STATUSES, isProcessable } from "@/lib/labels";
import { useSyncedState, useUrlState } from "@/lib/use-url-state";
import { cn } from "@/lib/utils";

type SortKey = "risk" | "leakage" | "claimed" | "admission" | "id";

const DEFAULTS = {
  page: "1",
  page_size: "50",
  status: "",
  tier: "",
  provider_id: "",
  action: "",
  split: "test",
  q: "",
  sort: "risk",
  order: "desc",
};

const STATUS_OPTIONS = CLAIM_STATUSES.map((s) => ({ value: s, label: CLAIM_STATUS_META[s].label }));
const TIER_OPTIONS = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];
const ACTION_OPTIONS = ACTIONS.map((a) => ({ value: a, label: ACTION_META[a].label }));
const SPLIT_OPTIONS = [
  { value: "test", label: "Test" },
  { value: "train", label: "Train" },
  { value: "live", label: "Live" },
];

const COLUMNS = 9;

export function ClaimsQueue() {
  const [state, update] = useUrlState(DEFAULTS);
  const { data: user } = useMe();
  const router = useRouter();
  const canProcess = hasRole(user?.role, ["adjuster", "manager", "admin"]);
  const canCreate = hasRole(user?.role, ["adjuster", "admin"]);

  const page = Math.max(1, Number(state.page) || 1);
  const pageSize = Number(state.page_size) || 50;
  const sort = state.sort as SortKey;
  const order = state.order === "asc" ? "asc" : "desc";

  const claims = useQuery({
    queryKey: [...claimsQueryKey, state],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/claims", {
          params: {
            query: {
              page,
              page_size: pageSize,
              status: state.status || undefined,
              tier: state.tier || undefined,
              provider_id: state.provider_id || undefined,
              action: state.action || undefined,
              split: state.split || undefined,
              q: state.q || undefined,
              sort,
              order,
            },
          },
        }),
      ) as Page<ClaimListItem>,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.items.some((c) => c.status === "processing") ? 3000 : false),
  });

  const providers = useProviders();

  const onSort = (key: SortKey) => {
    if (sort === key) update({ order: order === "desc" ? "asc" : "desc", page: "1" });
    else update({ sort: key, order: "desc", page: "1" });
  };

  const filtersActive =
    state.status || state.tier || state.provider_id || state.action || state.q || state.split !== DEFAULTS.split;

  const items = claims.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Claims"
        description="Claims waiting for review, highest risk first."
        actions={
          canCreate && (
            <Button asChild>
              <Link href="/claims/new">
                <Plus data-icon="inline-start" aria-hidden="true" />
                New claim
              </Link>
            </Button>
          )
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SearchBox value={state.q} onChange={(q) => update({ q, page: "1" })} />
        <FilterSelect label="Status" value={state.status} onChange={(v) => update({ status: v, page: "1" })} options={STATUS_OPTIONS} />
        <FilterSelect label="Risk" value={state.tier} onChange={(v) => update({ tier: v, page: "1" })} options={TIER_OPTIONS} />
        <FilterSelect label="Action" value={state.action} onChange={(v) => update({ action: v, page: "1" })} options={ACTION_OPTIONS} />
        <FilterSelect label="Split" value={state.split} onChange={(v) => update({ split: v, page: "1" })} options={SPLIT_OPTIONS} />
        <Combobox
          size="sm"
          className="w-56"
          aria-label="Filter by provider"
          value={state.provider_id}
          onChange={(v) => update({ provider_id: v, page: "1" })}
          options={(providers.data ?? []).map((p) => ({ value: p.id, label: p.name, hint: `${p.city}, ${p.id}` }))}
          placeholder="Provider: All"
          searchPlaceholder="Search provider, city or ID"
          emptyText="No provider matches."
          loading={providers.isPending}
          clearable
          clearLabel="All providers"
        />
        {filtersActive && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => update({ status: "", tier: "", provider_id: "", action: "", q: "", split: DEFAULTS.split, page: "1" })}
          >
            <X data-icon="inline-start" aria-hidden="true" />
            Clear filters
          </Button>
        )}
      </div>

      <Panel className="overflow-hidden">
        {/* Tighter cell padding below 1536px so all columns fit from 1280px. */}
        <Table className="max-2xl:[&_td]:px-1.5 max-2xl:[&_th]:px-1.5">
          <TableHeader>
            <TableRow>
              <SortableHead label="Claim" sortKey="id" sort={sort} order={order} onSort={onSort} />
              <TableHead>Provider and procedure</TableHead>
              <SortableHead label="Admitted" sortKey="admission" sort={sort} order={order} onSort={onSort} />
              <SortableHead label="Claimed" sortKey="claimed" sort={sort} order={order} onSort={onSort} numeric />
              <TableHead className="text-right">Payable</TableHead>
              <SortableHead label="Leakage" sortKey="leakage" sort={sort} order={order} onSort={onSort} numeric />
              <SortableHead label="Risk" sortKey="risk" sort={sort} order={order} onSort={onSort} />
              <TableHead>Recommended</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className={cn(claims.isFetching && claims.isPlaceholderData && "opacity-60 transition-opacity")}>
            <TableStateRows
              colSpan={COLUMNS}
              isLoading={claims.isPending}
              error={claims.isError ? getErrorMessage(claims.error) : null}
              onRetry={() => claims.refetch()}
              isEmpty={items.length === 0}
              emptyTitle={filtersActive ? "No claims match these filters" : "No claims yet"}
              emptyHint={
                filtersActive
                  ? "Clear a filter or search for a different claim ID."
                  : "Claims appear here once they are loaded or created."
              }
            />
            {items.map((c) => (
              <TableRow
                key={c.id}
                className="cursor-pointer"
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest("a,button")) return;
                  router.push(`/claims/${encodeURIComponent(c.id)}`);
                }}
              >
                <TableCell className="py-1.5">
                  <Link
                    href={`/claims/${encodeURIComponent(c.id)}`}
                    className="num rounded-sm font-semibold text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {c.id}
                  </Link>
                  <div className="text-xs text-muted-foreground" title="Member (masked)">
                    {c.member_masked}
                  </div>
                </TableCell>
                <TableCell className="max-w-40 py-1.5 2xl:max-w-72">
                  <div className="truncate" title={c.provider_name}>
                    {c.provider_name}
                  </div>
                  <div className="truncate text-xs text-muted-foreground" title={`${c.procedure_code} ${c.procedure_name}`}>
                    {c.procedure_name}
                  </div>
                </TableCell>
                <TableCell className="num text-muted-foreground" title={formatDate(c.admission_at)}>
                  {formatShortDate(c.admission_at)}
                </TableCell>
                <TableCell className="num text-right">{formatINR(c.claimed_amount)}</TableCell>
                <TableCell className="num text-right">{formatINR(c.payable_amount)}</TableCell>
                <TableCell
                  className={cn(
                    "num text-right",
                    c.leakage_amount && Number(c.leakage_amount) > 0 ? "font-semibold text-leakage" : "text-muted-foreground",
                  )}
                >
                  {formatINR(c.leakage_amount)}
                </TableCell>
                <TableCell>{isRiskLevel(c.tier) ? <RiskBadge level={c.tier} score={c.risk} /> : <Dash />}</TableCell>
                <TableCell>{isClaimAction(c.action) ? <ActionBadge action={c.action} compact /> : <Dash />}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {/* For people who can process, the button stands in for the "Received" state. */}
                    {!(canProcess && c.status === "received") && <ClaimStatusPill status={c.status} />}
                    {canProcess && isProcessable(c.status) && <ProcessButton claimId={c.id} />}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={pageSize}
          total={claims.data?.total}
          isFetching={claims.isFetching}
          onPage={(p) => update({ page: String(p) })}
          onPageSize={(s) => update({ page_size: String(s), page: "1" })}
        />
      </Panel>
    </>
  );
}

function Dash() {
  return <span className="text-muted-foreground/60">–</span>;
}

function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [draft, setDraft] = useSyncedState(value);
  useEffect(() => {
    if (draft === value) return;
    const t = setTimeout(() => onChange(draft.trim()), 300);
    return () => clearTimeout(t);
  }, [draft, value, onChange]);
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        type="search"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Search claim ID"
        aria-label="Search by claim ID"
        className="h-7 w-48 bg-card pl-8 text-[13px]"
      />
    </div>
  );
}

function ProcessButton({ claimId }: { claimId: string }) {
  const [jobId, setJobId] = useState<number | null>(null);
  const process = useProcessClaim();
  const queryClient = useQueryClient();
  const job = useJob(jobId, {
    onFinish: (j) => {
      void queryClient.invalidateQueries({ queryKey: claimsQueryKey });
      if (j.status === "failed") toast.error(`Processing ${claimId} failed`, { description: j.error ?? undefined });
      else toast.success(`${claimId} processed`);
      setJobId(null);
    },
  });

  const busy = process.isPending || (jobId !== null && job.data?.status !== "done" && job.data?.status !== "failed");
  if (busy) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground" aria-live="polite">
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        {job.data?.status === "running" ? "Running" : "Queued"}
      </span>
    );
  }
  return (
    <Button
      variant="outline"
      size="xs"
      className="bg-card"
      onClick={() =>
        process.mutate(claimId, {
          onSuccess: (id) => setJobId(id),
          onError: (e) => toast.error(getErrorMessage(e)),
        })
      }
    >
      <Play data-icon="inline-start" aria-hidden="true" />
      Process
    </Button>
  );
}

/** "15 Sep 26": keeps the date column narrow; the full date is in the tooltip. */
function formatShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit", timeZone: "UTC" });
}
