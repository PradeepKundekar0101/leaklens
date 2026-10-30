"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, CircleAlert, Inbox, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TableCell, TableHead, TableRow } from "@/components/ui/table";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export function SortableHead<K extends string>({
  label,
  sortKey,
  sort,
  order,
  onSort,
  numeric,
  className,
}: {
  label: string;
  sortKey: K;
  sort: string;
  order: "asc" | "desc";
  onSort: (key: K) => void;
  numeric?: boolean;
  className?: string;
}) {
  const active = sort === sortKey;
  const Icon = !active ? ArrowUpDown : order === "desc" ? ArrowDown : ArrowUp;
  return (
    <TableHead
      className={cn(numeric && "text-right", className)}
      aria-sort={active ? (order === "desc" ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "-mx-1 inline-flex items-center gap-1 rounded-sm px-1 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
          numeric && "flex-row-reverse",
          active && "text-foreground",
        )}
      >
        {label}
        <Icon className={cn("size-3", !active && "opacity-40")} aria-hidden="true" />
      </button>
    </TableHead>
  );
}

/** Loading, error and empty rows that span the table. Returns null when there are rows to show. */
export function TableStateRows({
  colSpan,
  isLoading,
  error,
  isEmpty,
  onRetry,
  emptyTitle = "Nothing to show",
  emptyHint,
  skeletonRows = 8,
}: {
  colSpan: number;
  isLoading: boolean;
  error?: string | null;
  isEmpty: boolean;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyHint?: React.ReactNode;
  skeletonRows?: number;
}) {
  if (isLoading) {
    return (
      <>
        {Array.from({ length: skeletonRows }, (_, i) => (
          <TableRow key={i} className="hover:bg-transparent">
            <TableCell colSpan={colSpan}>
              <Skeleton className="h-4 w-full" style={{ opacity: 1 - i * 0.08 }} />
            </TableCell>
          </TableRow>
        ))}
      </>
    );
  }
  if (error) {
    return (
      <TableRow className="hover:bg-transparent">
        <TableCell colSpan={colSpan} className="h-40 text-center whitespace-normal">
          <div className="mx-auto flex max-w-sm flex-col items-center">
            <CircleAlert className="mb-2 size-5 text-destructive" aria-hidden="true" />
            <p className="text-sm font-medium">Could not load this table</p>
            <p className="mt-0.5 text-[13px] text-muted-foreground">{error}</p>
            {onRetry && (
              <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
                <RefreshCw data-icon="inline-start" aria-hidden="true" />
                Try again
              </Button>
            )}
          </div>
        </TableCell>
      </TableRow>
    );
  }
  if (isEmpty) {
    return (
      <TableRow className="hover:bg-transparent">
        <TableCell colSpan={colSpan} className="h-40 text-center whitespace-normal">
          <div className="mx-auto flex max-w-sm flex-col items-center">
            <Inbox className="mb-2 size-5 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">{emptyTitle}</p>
            {emptyHint && <p className="mt-0.5 text-[13px] text-muted-foreground">{emptyHint}</p>}
          </div>
        </TableCell>
      </TableRow>
    );
  }
  return null;
}

export const PAGE_SIZES = [25, 50, 100] as const;

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
  isFetching,
}: {
  page: number;
  pageSize: number;
  total: number | undefined;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
  isFetching?: boolean;
}) {
  const pages = total ? Math.max(1, Math.ceil(total / pageSize)) : 1;
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = total ? Math.min(total, page * pageSize) : 0;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-2 text-[13px] text-muted-foreground">
      <div className="num" aria-live="polite">
        {total === undefined ? "Loading" : total === 0 ? "No results" : `${formatNumber(from)}–${formatNumber(to)} of ${formatNumber(total)}`}
        {isFetching && total !== undefined && <span className="ml-2 text-xs">Updating</span>}
      </div>
      <div className="flex items-center gap-3">
        {onPageSize && (
          <label className="flex items-center gap-2">
            <span>Rows</span>
            <Select value={String(pageSize)} onValueChange={(v) => onPageSize(Number(v))}>
              <SelectTrigger size="sm" className="w-[4.5rem] bg-card" aria-label="Rows per page">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
        )}
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            className="bg-card"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
          <span className="num min-w-[5.5rem] text-center">
            Page {formatNumber(page)} of {formatNumber(pages)}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            className="bg-card"
            aria-label="Next page"
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

/** A labelled select with an "All" option. `value` "" means no filter. */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel = "All",
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
  allLabel?: string;
  className?: string;
}) {
  return (
    <Select value={value || "__all"} onValueChange={(v) => onChange(v === "__all" ? "" : v)}>
      <SelectTrigger
        size="sm"
        aria-label={label}
        className={cn("min-w-32 bg-card text-[13px]", value && "border-primary/50", className)}
      >
        <span className="text-muted-foreground">{label}:</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all">{allLabel}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
