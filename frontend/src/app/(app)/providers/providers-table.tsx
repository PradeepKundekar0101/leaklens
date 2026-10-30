"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Pagination, SortableHead, TableStateRows } from "@/components/data-table";
import { PageHeader, Panel } from "@/components/page";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { Page, ProviderRow } from "@/lib/api/types";
import { formatINRCompact, formatINR, formatNumber, formatPercent } from "@/lib/format";
import { num } from "@/lib/labels";
import { useUrlState } from "@/lib/use-url-state";
import { cn } from "@/lib/utils";

type SortKey = "oe_index" | "flag_rate" | "leakage" | "claims";
const DEFAULTS = { page: "1", page_size: "50", sort: "oe_index" };
export const OE_ALERT = 1.2;

export function ProvidersTable() {
  const [state, update] = useUrlState(DEFAULTS);
  const router = useRouter();
  const page = Math.max(1, Number(state.page) || 1);
  const pageSize = Number(state.page_size) || 50;
  const sort = state.sort as SortKey;

  const providers = useQuery({
    queryKey: ["providers", state],
    queryFn: () => apiRequest<Page<ProviderRow>>("/api/v1/providers", { query: { page, page_size: pageSize, sort } }),
    placeholderData: keepPreviousData,
  });
  const items = providers.data?.items ?? [];
  const onSort = (key: SortKey) => update({ sort: key, page: "1" });

  return (
    <>
      <PageHeader
        title="Providers"
        description={
          <>
            Hospitals ranked by billing against expectation. An O/E index above {OE_ALERT} means the provider bills at least{" "}
            {Math.round((OE_ALERT - 1) * 100)}% more than peers for the same case mix.
          </>
        }
      />
      <Panel className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12 text-right">Rank</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead className="text-center">NABH</TableHead>
              <TableHead className="text-center">Network</TableHead>
              <SortableHead label="Claims" sortKey="claims" sort={sort} order="desc" onSort={onSort} numeric />
              <TableHead className="text-right">Claimed</TableHead>
              <SortableHead label="Leakage" sortKey="leakage" sort={sort} order="desc" onSort={onSort} numeric />
              <SortableHead label="Flag rate" sortKey="flag_rate" sort={sort} order="desc" onSort={onSort} numeric />
              <SortableHead label="O/E index" sortKey="oe_index" sort={sort} order="desc" onSort={onSort} numeric />
              <TableHead className="text-right">Pharmacy share vs peers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={11}
              isLoading={providers.isPending}
              error={providers.isError ? getErrorMessage(providers.error) : null}
              onRetry={() => providers.refetch()}
              isEmpty={items.length === 0}
              emptyTitle="No provider statistics yet"
              emptyHint="Statistics are computed from processed claims. A manager can refresh them from Admin."
            />
            {items.map((p) => {
              const oe = num(p.oe_index);
              const ph = num(p.avg_pharmacy_share);
              const peer = num(p.peer_pharmacy_share);
              return (
                <TableRow key={p.id} className="cursor-pointer" onClick={(e) => !(e.target as HTMLElement).closest("a") && router.push(`/providers/${encodeURIComponent(p.id)}`)}>
                  <TableCell className="num text-right text-muted-foreground">{p.rank}</TableCell>
                  <TableCell className="max-w-72">
                    <Link
                      href={`/providers/${encodeURIComponent(p.id)}`}
                      className="block truncate rounded-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {p.name}
                    </Link>
                    <div className="truncate text-xs text-muted-foreground">
                      {p.city} <span className="num">{p.id}</span>
                    </div>
                  </TableCell>
                  <TableCell className="num text-muted-foreground">
                    H{p.hospital_tier} / C{p.city_tier}
                  </TableCell>
                  <TableCell className="text-center">
                    <YesNo value={p.nabh} label="NABH accredited" />
                  </TableCell>
                  <TableCell className="text-center">
                    <YesNo value={p.network} label="In network" />
                  </TableCell>
                  <TableCell className="num text-right">{formatNumber(p.claims)}</TableCell>
                  <TableCell className="num text-right" title={formatINR(p.claimed_total)}>
                    {formatINRCompact(p.claimed_total)}
                  </TableCell>
                  <TableCell className="num text-right" title={formatINR(p.leakage_total)}>
                    {formatINRCompact(p.leakage_total)}
                  </TableCell>
                  <TableCell className="num text-right">{formatPercent(p.flag_rate)}</TableCell>
                  <TableCell className="text-right">
                    <OeValue value={oe} />
                  </TableCell>
                  <TableCell className="num text-right">
                    {formatPercent(ph)}
                    <span className="text-muted-foreground"> vs {formatPercent(peer)}</span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <Pagination
          page={page}
          pageSize={pageSize}
          total={providers.data?.total}
          isFetching={providers.isFetching}
          onPage={(p) => update({ page: String(p) })}
          onPageSize={(s) => update({ page_size: String(s), page: "1" })}
        />
      </Panel>
    </>
  );
}

export function OeValue({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground/60">–</span>;
  const alert = value > OE_ALERT;
  return (
    <span
      className={cn(
        "num inline-flex h-5 items-center rounded-[4px] px-1.5 text-[13px] font-semibold",
        alert ? "bg-risk-high/10 text-risk-high" : "text-foreground",
      )}
      title={alert ? `Bills ${Math.round((value - 1) * 100)}% above expected` : undefined}
    >
      {value.toFixed(2)}
    </span>
  );
}

function YesNo({ value, label }: { value: boolean; label: string }) {
  return value ? (
    <Check className="mx-auto size-3.5 text-action-approve" aria-label={label} />
  ) : (
    <Minus className="mx-auto size-3.5 text-muted-foreground/50" aria-label={`Not ${label.toLowerCase()}`} />
  );
}
