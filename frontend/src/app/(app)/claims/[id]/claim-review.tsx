"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Loader2, MessageSquareText, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { LoadError } from "@/components/app-shell/states";
import { ClaimStatusPill } from "@/components/claim-status";
import { Panel } from "@/components/page";
import { ActionBadge, isClaimAction, isRiskLevel, RiskBadge, ToneBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, getErrorMessage } from "@/lib/api/errors";
import type { ClaimDetail, ClaimPolicy, ClaimProvider, InvestigationReport } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { hasRole } from "@/lib/auth/roles";
import { claimQueryKey, claimsQueryKey, useProcessClaim } from "@/lib/claims";
import { formatDate, formatINR, formatNumber, formatPercent } from "@/lib/format";
import { useJob } from "@/lib/jobs";
import { humanize, isProcessable, roomLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

import { AnomalyTab } from "./anomaly-tab";
import { AuditTab } from "./audit-tab";
import { CopilotDrawer } from "./copilot";
import { DecisionPanel, ReviewHistory } from "./decision-panel";
import { DocumentsTab } from "./documents-tab";
import { InvestigationTab } from "./investigation-tab";
import { LineItemsTab } from "./line-items-tab";
import { RecommendationCard } from "./recommendation-card";
import { RulesTab } from "./rules-tab";
import { useClaim } from "./use-claim";

export function ClaimReview() {
  const { id: rawId } = useParams<{ id: string }>();
  const id = decodeURIComponent(rawId);
  const claim = useClaim(id);
  const { data: user } = useMe();
  const [tab, setTab] = useState("line-items");
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);

  if (claim.isError) {
    if (claim.error instanceof ApiError && claim.error.status === 404) {
      return (
        <div className="py-20 text-center">
          <h1 className="text-lg font-semibold">Claim {id} was not found</h1>
          <p className="mt-1 text-sm text-muted-foreground">Check the claim ID, or go back to the queue.</p>
          <Button asChild variant="outline" className="mt-5">
            <Link href="/claims">Back to claims</Link>
          </Button>
        </div>
      );
    }
    return <LoadError message={getErrorMessage(claim.error)} onRetry={() => claim.refetch()} />;
  }
  if (!claim.data) return <ReviewSkeleton />;

  const c = claim.data;
  const canCopilot = hasRole(user?.role, ["adjuster", "auditor"]);
  const showLine = (lineId: number) => {
    setSelectedLine(lineId);
    setTab("documents");
  };

  return (
    <>
      <ClaimHeader claim={c} canCopilot={canCopilot} onCopilot={() => setCopilotOpen(true)} />
      <AmountStrip claim={c} />

      {/* Below 1536px the recommendation and decision sit above the tabs, side by side, so the
          line-item table keeps the full width; on wide screens they become a right rail. */}
      <div className="mt-4 grid gap-4 2xl:grid-cols-[minmax(0,1fr)_22rem]">
        <aside className="grid min-w-0 content-start items-start gap-4 lg:grid-cols-2 2xl:col-start-2 2xl:row-start-1 2xl:grid-cols-1">
          <RecommendationCard claim={c} />
          {c.can_review ? <DecisionPanel claim={c} /> : <ReviewHistory claim={c} role={user?.role} />}
        </aside>
        <div className="min-w-0 2xl:col-start-1 2xl:row-start-1">
          <Tabs value={tab} onValueChange={setTab}>
            <div className="-mx-1 overflow-x-auto px-1 pb-0.5">
              <TabsList>
                <TabsTrigger value="line-items">
                  Line items <Count n={c.line_items.length} />
                </TabsTrigger>
                <TabsTrigger value="rules">
                  Rules <Count n={c.rule_findings.length} />
                </TabsTrigger>
                <TabsTrigger value="anomaly">Anomaly</TabsTrigger>
                {c.investigation && <TabsTrigger value="investigation">Investigation</TabsTrigger>}
                <TabsTrigger value="documents">
                  Documents <Count n={c.documents.length} />
                </TabsTrigger>
                <TabsTrigger value="audit">Audit</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="line-items" className="mt-3">
              <LineItemsTab claim={c} selectedLine={selectedLine} onSelectLine={setSelectedLine} onShowInDocument={showLine} />
            </TabsContent>
            <TabsContent value="rules" className="mt-3">
              <RulesTab claim={c} />
            </TabsContent>
            <TabsContent value="anomaly" className="mt-3">
              <AnomalyTab claim={c} />
            </TabsContent>
            {c.investigation && (
              <TabsContent value="investigation" className="mt-3">
                <InvestigationTab report={c.investigation as InvestigationReport} />
              </TabsContent>
            )}
            <TabsContent value="documents" className="mt-3">
              <DocumentsTab claim={c} selectedLine={selectedLine} onSelectLine={setSelectedLine} />
            </TabsContent>
            <TabsContent value="audit" className="mt-3">
              <AuditTab claimId={c.id} status={c.status} />
            </TabsContent>
          </Tabs>
        </div>

      </div>

      {canCopilot && <CopilotDrawer claimId={c.id} open={copilotOpen} onOpenChange={setCopilotOpen} />}
    </>
  );
}

function Count({ n }: { n: number }) {
  return <span className="num ml-1 text-xs font-normal text-muted-foreground">{n}</span>;
}

function ClaimHeader({ claim: c, canCopilot, onCopilot }: { claim: ClaimDetail; canCopilot: boolean; onCopilot: () => void }) {
  const { data: user } = useMe();
  const provider = c.provider as unknown as ClaimProvider;
  const policy = c.policy as unknown as ClaimPolicy;
  const canSeeProviders = hasRole(user?.role, ["auditor", "manager", "admin"]);
  const canProcess = hasRole(user?.role, ["adjuster", "manager", "admin"]);
  return (
    <div className="mb-4">
      <Link
        href="/claims"
        className="-ml-1 mb-2 inline-flex items-center gap-0.5 rounded-sm px-1 text-[13px] font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="size-3.5" aria-hidden="true" />
        Claims
      </Link>
      <div>
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h1 className="text-xl leading-7 font-semibold tracking-[-0.01em]">
              Claim <span className="num">{c.id}</span>
            </h1>
            <ClaimStatusPill status={c.status} />
            {isRiskLevel(c.anomaly?.tier) && <RiskBadge level={c.anomaly.tier} score={c.anomaly.risk} />}
            <ToneBadge className="font-medium">{humanize(c.split)}</ToneBadge>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {canProcess && (isProcessable(c.status) || c.status === "processing") && <ProcessClaimButton claim={c} />}
            {canCopilot && (
              <Button variant="outline" onClick={onCopilot} className="bg-card">
                <MessageSquareText data-icon="inline-start" aria-hidden="true" />
                Ask copilot
              </Button>
            )}
          </div>
        </div>
          <dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
            <Meta label="Provider">
              {canSeeProviders ? (
                <Link href={`/providers/${encodeURIComponent(provider.id)}`} className="font-medium text-primary hover:underline">
                  {provider.name}
                </Link>
              ) : (
                <span className="font-medium">{provider.name}</span>
              )}
              <span className="text-muted-foreground">
                , {provider.city}, tier {provider.hospital_tier}
                {provider.nabh ? ", NABH" : ""}
                {provider.network ? ", network" : ", non-network"}
              </span>
            </Meta>
            <Meta label="Procedure">
              <span className="font-medium">{c.procedure_name}</span>{" "}
              <span className="num text-muted-foreground">({c.procedure_code}, dx {c.diagnosis_code})</span>
            </Meta>
            <Meta label="Stay">
              <span className="num">
                {formatDate(c.admission_at)} to {formatDate(c.discharge_at)}
              </span>{" "}
              <span className="text-muted-foreground">
                ({formatNumber(c.los)} {c.los === 1 ? "day" : "days"}, {roomLabel(c.room_category)})
              </span>
            </Meta>
            <Meta label="Policy">
              <span className="font-medium">{policy.product_id}</span>
              <span className="num text-muted-foreground">
                , SI {formatINR(policy.sum_insured)}, balance {formatINR(policy.balance)}
              </span>
            </Meta>
            <Meta label="Type">{humanize(c.claim_type)}</Meta>
          </dl>
      </div>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline gap-1.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function ProcessClaimButton({ claim }: { claim: ClaimDetail }) {
  const [jobId, setJobId] = useState<number | null>(null);
  const process = useProcessClaim();
  const queryClient = useQueryClient();
  const job = useJob(jobId, {
    onFinish: (j) => {
      void queryClient.invalidateQueries({ queryKey: claimQueryKey(claim.id) });
      void queryClient.invalidateQueries({ queryKey: claimsQueryKey });
      if (j.status === "failed") toast.error("Processing failed", { description: j.error ?? undefined });
      setJobId(null);
    },
  });
  const running = claim.status === "processing" || process.isPending || (jobId !== null && !!job.data && job.data.status !== "done");
  const parsing = claim.documents.some((d) => d.parse_status === "pending" || d.parse_status === "parsing");
  return (
    <Button
      disabled={running || parsing}
      title={parsing ? "Wait for the documents to finish parsing" : undefined}
      onClick={() =>
        process.mutate(claim.id, {
          onSuccess: setJobId,
          onError: (e) => toast.error(getErrorMessage(e)),
        })
      }
    >
      {running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play data-icon="inline-start" aria-hidden="true" />}
      {running ? "Processing" : claim.status === "failed" ? "Process again" : "Process claim"}
    </Button>
  );
}

function AmountStrip({ claim: c }: { claim: ClaimDetail }) {
  const rec = c.recommendation;
  const leak = rec ? Number(rec.leakage_amount) : 0;
  return (
    <Panel className="grid grid-cols-2 divide-border sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
      <Stat label="Claimed" value={formatINR(c.claimed_amount)} />
      <Stat label="Payable" value={rec ? formatINR(rec.payable_amount) : "–"} muted={!rec} />
      <Stat
        label="Leakage"
        value={rec ? formatINR(rec.leakage_amount) : "–"}
        muted={!rec}
        className={cn(leak > 0 && "text-leakage")}
        sub={rec && Number(c.claimed_amount) > 0 ? `${formatPercent(leak / Number(c.claimed_amount))} of claimed` : undefined}
      />
      <Stat
        label="Member share"
        value={rec ? formatINR(rec.member_share) : "–"}
        muted={!rec}
        sub={rec ? "Co-pay and deductible" : undefined}
      />
      <div className="col-span-2 px-4 py-3 sm:col-span-1">
        <div className="text-xs font-medium text-muted-foreground">Recommended</div>
        {rec && isClaimAction(rec.action) ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <ActionBadge action={rec.action} />
            <span className="num text-xs text-muted-foreground" title="Model confidence">
              {formatPercent(rec.confidence, { digits: 0 })} confidence
            </span>
          </div>
        ) : (
          <div className="mt-1 text-lg font-semibold text-muted-foreground/70">–</div>
        )}
      </div>
    </Panel>
  );
}

function Stat({
  label,
  value,
  sub,
  muted,
  className,
}: {
  label: string;
  value: string;
  sub?: string;
  muted?: boolean;
  className?: string;
}) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className={cn("num mt-0.5 truncate text-lg leading-7 font-semibold", muted && "text-muted-foreground/70", className)}>
        {value}
      </div>
      {sub && <div className="num text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading claim" className="space-y-4">
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-7 w-72" />
      <Skeleton className="h-4 w-full max-w-3xl" />
      <Skeleton className="h-20 w-full" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  );
}
