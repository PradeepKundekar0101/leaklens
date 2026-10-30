"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { ClauseText } from "@/lib/api/types";

/** Finds `quote` in `text` ignoring whitespace differences and case. Exported for tests. */
export function findQuote(text: string, quote: string | null | undefined): [number, number] | null {
  if (!quote) return null;
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const match = new RegExp(pattern, "i").exec(text);
  return match ? [match.index, match.index + match[0].length] : null;
}

export function ClauseDialog({
  productId,
  clauseNo,
  quote,
  verified,
  open,
  onOpenChange,
}: {
  productId: string;
  clauseNo: string;
  quote?: string | null;
  verified: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const clause = useQuery({
    queryKey: ["clause", productId, clauseNo],
    queryFn: () =>
      apiRequest<ClauseText>(`/api/v1/policies/${encodeURIComponent(productId)}/clauses/${encodeURIComponent(clauseNo)}`),
    enabled: open,
    staleTime: Infinity,
  });
  const range = clause.data ? findQuote(clause.data.text, quote) : null;
  // A highlight is only shown for citations the backend verified; an unverified quote that
  // happens to match is still not presented as verified.
  const highlight = verified ? range : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Clause <span className="num">{clauseNo}</span>
          </DialogTitle>
          <DialogDescription>
            {productId}
            {clause.data?.section_path ? `, ${clause.data.section_path}` : ""}
            {clause.data?.page ? `, page ${clause.data.page}` : ""}
          </DialogDescription>
        </DialogHeader>

        {verified ? (
          <p className="flex items-center gap-1.5 text-xs font-medium text-action-approve">
            <CircleCheck className="size-3.5" aria-hidden="true" />
            Verified: the quoted text appears in this clause.
          </p>
        ) : (
          <p className="flex items-start gap-1.5 rounded-md border border-action-investigate/30 bg-action-investigate/8 px-2.5 py-2 text-xs text-action-investigate">
            <CircleAlert className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            Unverified citation: the quote could not be matched to the policy wording. Treat the verdict with care.
          </p>
        )}

        {quote && (
          <blockquote className="border-l-2 border-primary/40 pl-3 text-[13px] text-muted-foreground italic">
            {quote}
          </blockquote>
        )}

        <div className="-mx-6 min-h-24 overflow-y-auto border-t px-6 pt-3">
          {clause.isPending ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          ) : clause.isError ? (
            <p className="text-[13px] text-destructive">{getErrorMessage(clause.error)}</p>
          ) : (
            <p className="max-w-[75ch] pb-2 text-[13px] leading-6 whitespace-pre-line">
              {highlight ? (
                <>
                  {clause.data.text.slice(0, highlight[0])}
                  <mark className="rounded-[2px] bg-primary/15 px-0.5 text-foreground">
                    {clause.data.text.slice(highlight[0], highlight[1])}
                  </mark>
                  {clause.data.text.slice(highlight[1])}
                </>
              ) : (
                clause.data.text
              )}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
