"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { Panel, PanelHeader } from "@/components/page";
import { ACTION_META, ACTIONS, ActionBadge, type ClaimAction, isClaimAction } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/client";
import { getErrorMessage, unwrap } from "@/lib/api/errors";
import type { ClaimDetail } from "@/lib/api/types";
import { claimQueryKey, claimsQueryKey } from "@/lib/claims";
import { formatDateTime, formatINR, toPaise } from "@/lib/format";
import { cn } from "@/lib/utils";

const DECISION_LABELS: Record<ClaimAction, string> = {
  approve: "Approve",
  approve_with_deductions: "Approve a different amount",
  query: "Query",
  investigate: "Investigate",
  refer_siu: "Refer to SIU",
  reject: "Reject",
};

export function DecisionPanel({ claim }: { claim: ClaimDetail }) {
  const rec = claim.recommendation!;
  const recAction: ClaimAction = isClaimAction(rec.action) ? rec.action : "approve";
  const [decision, setDecision] = useState<ClaimAction>(recAction);
  const [amount, setAmount] = useState(trimZeros(rec.payable_amount));
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const queryClient = useQueryClient();
  const ids = { amount: useId(), notes: useId(), group: useId() };

  const effectiveAmount = decision === "reject" ? "0" : amount;
  const amountPaise = toPaise(effectiveAmount);
  const claimedPaise = toPaise(claim.claimed_amount) ?? BigInt(0);
  const amountError =
    amountPaise === null || amountPaise < BigInt(0)
      ? "Enter an amount in rupees."
      : amountPaise > claimedPaise
        ? `Cannot exceed the claimed ${formatINR(claim.claimed_amount)}.`
        : null;
  const overriding = decision !== recAction || amountPaise !== toPaise(rec.payable_amount);
  const notesError = overriding && !notes.trim() ? "Add a note: you are changing the recommended decision or amount." : null;

  const submit = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/claims/{claim_id}/review", {
          params: { path: { claim_id: claim.id } },
          body: { decision, final_amount: effectiveAmount, notes: notes.trim() || null },
        }),
      ) as { ok: boolean; errors?: string[] },
    onSuccess: (res) => {
      if (res.errors && res.errors.length) toast.warning("Decision recorded with warnings", { description: res.errors.join("; ") });
      else toast.success(`Decision recorded: ${ACTION_META[decision].label}`);
      void queryClient.invalidateQueries({ queryKey: claimQueryKey(claim.id) });
      void queryClient.invalidateQueries({ queryKey: claimsQueryKey });
    },
  });

  return (
    <Panel>
      <PanelHeader title="Your decision" description="The recommendation is preselected. Change it if you disagree." />
      <form
        className="space-y-4 px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(true);
          if (!amountError && !notesError) submit.mutate();
        }}
        noValidate
      >
        <fieldset>
          <legend className="sr-only">Decision</legend>
          <div className="grid grid-cols-2 gap-1.5" role="radiogroup" aria-labelledby={ids.group}>
            {ACTIONS.map((a) => {
              const selected = decision === a;
              return (
                <button
                  key={a}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setDecision(a)}
                  style={{ "--tone": `var(${ACTION_META[a].tone})` } as React.CSSProperties}
                  className={cn(
                    "flex min-h-9 items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-left text-[13px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                    selected
                      ? "border-[color-mix(in_oklch,var(--tone)_55%,transparent)] bg-[color-mix(in_oklch,var(--tone)_10%,transparent)] text-(--tone)"
                      : "hover:bg-accent",
                  )}
                >
                  {(() => {
                    const Icon = ACTION_META[a].icon;
                    return <Icon className="size-3.5 shrink-0" strokeWidth={2.5} aria-hidden="true" />;
                  })()}
                  <span className="leading-tight">{DECISION_LABELS[a]}</span>
                  {a === recAction && <span className="sr-only">(recommended)</span>}
                </button>
              );
            })}
          </div>
          <p id={ids.group} className="mt-1.5 text-xs text-muted-foreground">
            Recommended: {ACTION_META[recAction].label}, {formatINR(rec.payable_amount)}
          </p>
        </fieldset>

        <div className="space-y-1.5">
          <Label htmlFor={ids.amount}>Final amount</Label>
          <div className="relative">
            <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">₹</span>
            <Input
              id={ids.amount}
              inputMode="decimal"
              value={decision === "reject" ? "0" : amount}
              disabled={decision === "reject"}
              onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
              aria-invalid={submitted && !!amountError}
              aria-describedby={`${ids.amount}-hint`}
              className="num h-9 pl-6"
            />
          </div>
          <p id={`${ids.amount}-hint`} className={cn("text-xs", submitted && amountError ? "text-destructive" : "text-muted-foreground")}>
            {submitted && amountError
              ? amountError
              : decision === "reject"
                ? "A rejected claim pays nothing."
                : amountPaise !== null
                  ? `${formatINR(effectiveAmount)} of ${formatINR(claim.claimed_amount)} claimed`
                  : " "}
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={ids.notes}>
            Notes {overriding ? <span className="text-destructive">required</span> : <span className="font-normal text-muted-foreground">optional</span>}
          </Label>
          <Textarea
            id={ids.notes}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            maxLength={4000}
            placeholder={overriding ? "Why you are departing from the recommendation" : "Anything the next reviewer should know"}
            aria-invalid={submitted && !!notesError}
            aria-describedby={notesError ? `${ids.notes}-err` : undefined}
          />
          {submitted && notesError && (
            <p id={`${ids.notes}-err`} className="text-xs text-destructive">
              {notesError}
            </p>
          )}
        </div>

        {submit.isError && <p className="text-[13px] text-destructive" role="alert">{getErrorMessage(submit.error)}</p>}

        <Button type="submit" className="h-9 w-full" disabled={submit.isPending}>
          {submit.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
          Submit decision
        </Button>
      </form>
    </Panel>
  );
}

export function ReviewHistory({ claim, role }: { claim: ClaimDetail; role?: string }) {
  if (claim.reviews.length === 0) {
    if (!claim.awaiting_review) return null;
    return (
      <Panel className="px-4 py-3 text-[13px] text-muted-foreground">
        {role === "adjuster"
          ? "This claim is waiting for review."
          : "Waiting for an adjuster's decision. Your role can view this claim but not decide it."}
      </Panel>
    );
  }
  return (
    <Panel>
      <PanelHeader title="Decision" />
      <ul className="divide-y">
        {claim.reviews.map((r) => (
          <li key={r.id} className="space-y-1.5 px-4 py-3 text-[13px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              {isClaimAction(r.decision) ? <ActionBadge action={r.decision} /> : <span>{r.decision}</span>}
              <span className="num font-semibold">{formatINR(r.final_amount)}</span>
            </div>
            {r.notes && <p className="whitespace-pre-line">{r.notes}</p>}
            <p className="text-xs text-muted-foreground">
              {r.reviewer_name ?? `User ${r.reviewer_id}`}, {formatDateTime(r.created_at)}
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function trimZeros(amount: string): string {
  return amount.replace(/\.00$/, "");
}
