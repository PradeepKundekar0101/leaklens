import {
  Check,
  CircleHelp,
  type LucideIcon,
  Minus,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * Tinted status badge. Every colour derives from one `--tone` token so the same markup
 * works in light and dark mode: text in the tone, a 10% wash and a 28% outline.
 */
export function ToneBadge({
  tone = "--muted-foreground",
  className,
  children,
  title,
}: {
  tone?: string;
  className?: string;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      style={{ "--tone": `var(${tone})` } as CSSProperties}
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-[4px] border px-1.5 text-xs leading-none font-semibold whitespace-nowrap",
        "border-[color-mix(in_oklch,var(--tone)_30%,transparent)] bg-[color-mix(in_oklch,var(--tone)_10%,transparent)] text-(--tone)",
        className,
      )}
    >
      {children}
    </span>
  );
}

export const RISK_LEVELS = ["low", "medium", "high"] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

const RISK_META: Record<RiskLevel, { label: string; tone: string }> = {
  low: { label: "Low", tone: "--risk-low" },
  medium: { label: "Medium", tone: "--risk-medium" },
  high: { label: "High", tone: "--risk-high" },
};

export function isRiskLevel(value: unknown): value is RiskLevel {
  return typeof value === "string" && (RISK_LEVELS as readonly string[]).includes(value);
}

export function RiskBadge({ level, score, className }: { level: RiskLevel; score?: number | null; className?: string }) {
  const meta = RISK_META[level];
  const scoreText = score === null || score === undefined ? null : score.toFixed(2);
  return (
    <ToneBadge
      tone={meta.tone}
      className={className}
      title={scoreText ? `${meta.label} risk, score ${scoreText}` : `${meta.label} risk`}
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {meta.label}
      {scoreText && <span className="num font-medium opacity-80">{scoreText}</span>}
    </ToneBadge>
  );
}

export const ACTIONS = [
  "approve",
  "approve_with_deductions",
  "investigate",
  "refer_siu",
  "query",
  "reject",
] as const;
export type ClaimAction = (typeof ACTIONS)[number];

export const ACTION_META: Record<ClaimAction, { label: string; short: string; tone: string; icon: LucideIcon }> = {
  approve: { label: "Approve", short: "Approve", tone: "--action-approve", icon: Check },
  approve_with_deductions: {
    label: "Approve with deductions",
    short: "Approve, deduct",
    tone: "--action-approve-with-deductions",
    icon: Minus,
  },
  investigate: { label: "Investigate", short: "Investigate", tone: "--action-investigate", icon: Search },
  refer_siu: { label: "Refer to SIU", short: "Refer to SIU", tone: "--action-refer-siu", icon: ShieldAlert },
  query: { label: "Query", short: "Query", tone: "--action-query", icon: CircleHelp },
  reject: { label: "Reject", short: "Reject", tone: "--action-reject", icon: X },
};

export function isClaimAction(value: unknown): value is ClaimAction {
  return typeof value === "string" && (ACTIONS as readonly string[]).includes(value);
}

export function ActionBadge({
  action,
  compact = false,
  className,
}: {
  action: ClaimAction;
  /** Shorter label for narrow table columns; the full label stays in the tooltip. */
  compact?: boolean;
  className?: string;
}) {
  const meta = ACTION_META[action];
  const Icon = meta.icon;
  return (
    <ToneBadge tone={meta.tone} className={className} title={meta.label}>
      <Icon aria-hidden="true" className="size-3" strokeWidth={2.5} />
      {compact ? meta.short : meta.label}
    </ToneBadge>
  );
}

/** Neutral-or-toned pill for workflow states (claim status, parse status, job status). */
export function StatusPill({ label, tone, className }: { label: string; tone?: string; className?: string }) {
  return (
    <ToneBadge tone={tone} className={cn("font-medium", className)}>
      {label}
    </ToneBadge>
  );
}
