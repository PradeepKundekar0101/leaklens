"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, FileSearch, PencilLine } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Panel } from "@/components/page";
import { ToneBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api/client";
import { getErrorMessage, unwrap } from "@/lib/api/errors";
import type { ClaimDetail, ClaimPolicy, CoverageFinding, LineItem, RuleFinding } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { claimQueryKey } from "@/lib/claims";
import { formatINR, formatNumber, toPaise } from "@/lib/format";
import { CATEGORY_LABELS, COVERAGE_META, COVERAGE_VERDICTS, type CoverageVerdict, humanize, RULE_NAMES, SEVERITY_TONE } from "@/lib/labels";
import { cn } from "@/lib/utils";

import { ClauseDialog } from "./clause-dialog";

export function LineItemsTab({
  claim,
  selectedLine,
  onSelectLine,
  onShowInDocument,
}: {
  claim: ClaimDetail;
  selectedLine: number | null;
  onSelectLine: (id: number | null) => void;
  onShowInDocument: (id: number) => void;
}) {
  const { data: user } = useMe();
  const canOverride = user?.role === "adjuster";
  const policy = claim.policy as unknown as ClaimPolicy;

  const findingsByLine = groupBy(claim.rule_findings, (f) => f.line_item_id);
  const coverageByLine = groupBy(claim.coverage_findings, (f) => f.line_item_id);
  const claimLevel = claim.rule_findings.filter((f) => f.line_item_id === null);
  const hasAllowed = claim.line_items.some((li) => li.allowed_amount !== null);
  const hasFindings = claim.line_items.some((li) => li.non_payable || findingsByLine.has(li.id));
  const hasCoverage = claim.coverage_findings.some((f) => f.line_item_id !== null);
  const hasImpact = hasFindings || claim.line_items.some((li) => li.allowed_amount !== null && Number(li.allowed_amount) < Number(li.amount));

  if (claim.line_items.length === 0) {
    return (
      <Panel className="px-4 py-10 text-center">
        <p className="text-sm font-medium">No line items yet</p>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Line items appear once the bill is uploaded and parsed, or the claim is loaded with its bill.
        </p>
      </Panel>
    );
  }

  const totals = claim.line_items.reduce(
    (acc, li) => {
      acc.amount += toPaise(li.amount) ?? BigInt(0);
      if (li.allowed_amount !== null) acc.allowed += toPaise(li.allowed_amount) ?? BigInt(0);
      return acc;
    },
    { amount: BigInt(0), allowed: BigInt(0) },
  );

  return (
    <div className="space-y-3">
      {claimLevel.length > 0 && (
        <Panel className="px-4 py-3">
          <h3 className="mb-1.5 text-xs font-semibold text-muted-foreground">Claim-level findings</h3>
          <ul className="space-y-1">
            {claimLevel.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="flex items-center gap-2">
                  <RuleBadge finding={f} />
                  {f.clause_ref && <span className="text-xs text-muted-foreground">clause {f.clause_ref}</span>}
                </span>
                <span className={cn("num font-semibold", Number(f.amount_impact) > 0 ? "text-leakage" : "text-muted-foreground")}>
                  {formatINR(negate(f.amount_impact))}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Unit price</TableHead>
              <TableHead className="text-right">MRP</TableHead>
              <TableHead className="text-right">Billed</TableHead>
              {hasAllowed && <TableHead className="text-right">Allowed</TableHead>}
              {hasImpact && <TableHead className="text-right">Impact</TableHead>}
              {hasFindings && <TableHead>Findings</TableHead>}
              {hasCoverage && <TableHead>Coverage</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {claim.line_items.map((li) => {
              const findings = findingsByLine.get(li.id) ?? [];
              const coverage = coverageByLine.get(li.id) ?? [];
              const impact = lineImpact(li, findings);
              const selected = selectedLine === li.id;
              return (
                <TableRow
                  key={li.id}
                  data-state={selected ? "selected" : undefined}
                  onClick={() => onSelectLine(selected ? null : li.id)}
                  className="cursor-pointer align-top"
                >
                  <TableCell className="min-w-56 whitespace-normal">
                    <div className="flex items-start gap-1.5">
                      <div className="min-w-0">
                        <div className="font-medium">{li.description}</div>
                        <div className="num text-xs text-muted-foreground">
                          {CATEGORY_LABELS[li.category] ?? humanize(li.category)}
                          {li.item_code && !["ROOM", "ICU", "NURSING", "OT", "SURGEON"].includes(li.item_code) && `, ${li.item_code}`}
                          , {formatShortDate(li.service_date)}
                          {li.page !== null && `, p. ${li.page}`}
                        </div>
                      </div>
                      {li.document_id !== null && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-xs"
                              className="ml-auto shrink-0 text-muted-foreground"
                              aria-label={`Show ${li.description} in the document`}
                              onClick={(e) => {
                                e.stopPropagation();
                                onShowInDocument(li.id);
                              }}
                            >
                              <FileSearch aria-hidden="true" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Show in document</TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="num text-right">{formatNumber(Number(li.qty))}</TableCell>
                  <TableCell className="num text-right">{formatINR(li.unit_price)}</TableCell>
                  <TableCell className={cn("num text-right", li.mrp && Number(li.unit_price) > Number(li.mrp) && "font-semibold text-leakage")}>
                    {li.mrp ? formatINR(li.mrp) : <span className="text-muted-foreground/60">–</span>}
                  </TableCell>
                  <TableCell className="num text-right">{formatINR(li.amount)}</TableCell>
                  {hasAllowed && (
                    <TableCell className={cn("num text-right", li.allowed_amount !== null && li.allowed_amount !== li.amount && Number(li.allowed_amount) < Number(li.amount) && "font-semibold")}>
                      {li.allowed_amount !== null ? formatINR(li.allowed_amount) : <span className="text-muted-foreground/60">–</span>}
                    </TableCell>
                  )}
                  {hasImpact && (
                    <TableCell className={cn("num text-right", impact > BigInt(0) && "font-semibold text-leakage")}>
                      {impact > BigInt(0) ? formatINR(`-${paiseToString(impact)}`) : <span className="text-muted-foreground/60">–</span>}
                    </TableCell>
                  )}
                  {hasFindings && (
                  <TableCell className="whitespace-normal">
                    <div className="flex max-w-56 flex-wrap gap-1">
                      {li.non_payable && <ToneBadge tone="--action-reject">Non-payable</ToneBadge>}
                      {findings.map((f) => (
                        <RuleBadge key={f.id} finding={f} />
                      ))}
                    </div>
                  </TableCell>
                  )}
                  {hasCoverage && (
                  <TableCell className="whitespace-normal">
                    <div className="flex flex-col items-start gap-1">
                      {coverage.map((cf) => (
                        <CoverageChip
                          key={cf.id}
                          finding={cf}
                          claimId={claim.id}
                          productId={policy.product_id}
                          canOverride={canOverride}
                        />
                      ))}
                      {coverage.length === 0 && <span className="text-muted-foreground/60">–</span>}
                    </div>
                  </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
          <tfoot>
            <TableRow className="border-t bg-(--table-head) font-semibold hover:bg-(--table-head)">
              <TableCell>Total</TableCell>
              <TableCell colSpan={3} />
              <TableCell className="num text-right">{formatINR(paiseToString(totals.amount))}</TableCell>
              {hasAllowed && <TableCell className="num text-right">{formatINR(paiseToString(totals.allowed))}</TableCell>}
              {(hasImpact || hasFindings || hasCoverage) && <TableCell colSpan={Number(hasImpact) + Number(hasFindings) + Number(hasCoverage)} />}
            </TableRow>
          </tfoot>
        </Table>
      </Panel>
    </div>
  );
}

function RuleBadge({ finding }: { finding: RuleFinding }) {
  return (
    <ToneBadge
      tone={SEVERITY_TONE[finding.severity] ?? "--risk-medium"}
      title={`${finding.rule_code} ${RULE_NAMES[finding.rule_code] ?? finding.rule_name}: ${formatINR(finding.amount_impact)}${finding.clause_ref ? `, clause ${finding.clause_ref}` : ""}`}
    >
      <span className="num">{finding.rule_code}</span>
      <span className="font-medium">{finding.rule_name}</span>
    </ToneBadge>
  );
}

function CoverageChip({
  finding,
  claimId,
  productId,
  canOverride,
}: {
  finding: CoverageFinding;
  claimId: string;
  productId: string;
  canOverride: boolean;
}) {
  const [clauseOpen, setClauseOpen] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const overridden = finding.overridden as { from?: string; to?: string; note?: string } | null;
  const verdict = (overridden?.to ?? finding.verdict) as CoverageVerdict;
  const meta = COVERAGE_META[verdict] ?? { label: humanize(verdict), tone: "--muted-foreground" };

  return (
    <div className="flex flex-wrap items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <ToneBadge tone={meta.tone} title={`${finding.reason} (confidence ${Math.round(finding.confidence * 100)}%)`}>
        {meta.label}
      </ToneBadge>
      {finding.clause_no && (
        <button
          type="button"
          onClick={() => setClauseOpen(true)}
          className={cn(
            "inline-flex h-5 items-center gap-1 rounded-[4px] border px-1.5 text-xs font-medium outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
            finding.verified ? "text-foreground" : "border-dashed border-action-investigate/50 text-action-investigate",
          )}
          aria-label={`Clause ${finding.clause_no}, ${finding.verified ? "verified" : "unverified"} citation`}
        >
          {finding.verified ? (
            <CircleCheck className="size-3 text-action-approve" aria-hidden="true" />
          ) : (
            <CircleAlert className="size-3" aria-hidden="true" />
          )}
          <span className="num">Cl. {finding.clause_no}</span>
          {!finding.verified && <span>unverified</span>}
        </button>
      )}
      {overridden && (
        <span className="text-xs text-muted-foreground" title={overridden.note}>
          overridden from {COVERAGE_META[overridden.from as CoverageVerdict]?.label.toLowerCase() ?? overridden.from}
        </span>
      )}
      {canOverride && (
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground"
          aria-label="Override coverage verdict"
          onClick={() => setOverrideOpen(true)}
        >
          <PencilLine aria-hidden="true" />
        </Button>
      )}
      {finding.clause_no && (
        <ClauseDialog
          productId={productId}
          clauseNo={finding.clause_no}
          quote={finding.quote}
          verified={finding.verified}
          open={clauseOpen}
          onOpenChange={setClauseOpen}
        />
      )}
      {canOverride && (
        <OverrideDialog claimId={claimId} finding={finding} current={verdict} open={overrideOpen} onOpenChange={setOverrideOpen} />
      )}
    </div>
  );
}

function OverrideDialog({
  claimId,
  finding,
  current,
  open,
  onOpenChange,
}: {
  claimId: string;
  finding: CoverageFinding;
  current: CoverageVerdict;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [verdict, setVerdict] = useState<CoverageVerdict>(current);
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/claims/{claim_id}/coverage/{finding_id}/override", {
          params: { path: { claim_id: claimId, finding_id: finding.id } },
          body: { verdict, note: note.trim() },
        }),
      ),
    onSuccess: () => {
      toast.success("Coverage verdict overridden");
      void queryClient.invalidateQueries({ queryKey: claimQueryKey(claimId) });
      onOpenChange(false);
      setNote("");
    },
  });
  const noteOk = note.trim().length >= 3;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Override coverage verdict</DialogTitle>
          <DialogDescription>
            Your note is saved against clause {finding.clause_no ?? "–"} and used in future coverage checks.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (noteOk) save.mutate();
          }}
        >
          <RadioGroup value={verdict} onValueChange={(v) => setVerdict(v as CoverageVerdict)} className="grid grid-cols-2 gap-2">
            {COVERAGE_VERDICTS.map((v) => (
              <Label
                key={v}
                htmlFor={`verdict-${finding.id}-${v}`}
                className="flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 text-[13px] font-medium has-data-[state=checked]:border-primary/60 has-data-[state=checked]:bg-primary/5"
              >
                <RadioGroupItem id={`verdict-${finding.id}-${v}`} value={v} />
                {COVERAGE_META[v].label}
              </Label>
            ))}
          </RadioGroup>
          <div className="space-y-1.5">
            <Label htmlFor={`note-${finding.id}`}>Reason</Label>
            <Textarea
              id={`note-${finding.id}`}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Why this item is covered differently"
              rows={3}
              required
              minLength={3}
            />
          </div>
          {save.isError && <p className="text-[13px] text-destructive">{getErrorMessage(save.error)}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!noteOk || save.isPending || verdict === current}>
              Save override
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function groupBy<T, K>(items: T[], key: (t: T) => K): Map<K, T[]> {
  const map = new Map<K, T[]>();
  for (const item of items) {
    const k = key(item);
    map.set(k, [...(map.get(k) ?? []), item]);
  }
  return map;
}

/** Rupees deducted from a line: billed minus allowed when known, else the rule impacts. */
function lineImpact(li: LineItem, findings: RuleFinding[]): bigint {
  if (li.allowed_amount !== null) {
    const d = (toPaise(li.amount) ?? BigInt(0)) - (toPaise(li.allowed_amount) ?? BigInt(0));
    return d > BigInt(0) ? d : BigInt(0);
  }
  return findings.reduce((acc, f) => acc + (toPaise(f.amount_impact) ?? BigInt(0)), BigInt(0));
}

export function paiseToString(p: bigint): string {
  const neg = p < BigInt(0);
  const abs = neg ? -p : p;
  return `${neg ? "-" : ""}${abs / BigInt(100)}.${(abs % BigInt(100)).toString().padStart(2, "0")}`;
}

export function negate(amount: string): string {
  const p = toPaise(amount);
  return p === null ? amount : paiseToString(-p);
}

function formatShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}
