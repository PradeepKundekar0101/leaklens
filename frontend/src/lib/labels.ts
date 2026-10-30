import { formatINR, formatNumber, formatPercent } from "./format";

export const CLAIM_STATUSES = [
  "received",
  "processing",
  "pending_review",
  "approved",
  "approved_with_deductions",
  "queried",
  "investigating",
  "rejected",
  "failed",
] as const;
export type ClaimStatus = (typeof CLAIM_STATUSES)[number];

/** `tone` is a CSS variable name used by StatusPill; neutral when undefined. */
export const CLAIM_STATUS_META: Record<ClaimStatus, { label: string; tone?: string }> = {
  received: { label: "Received" },
  processing: { label: "Processing", tone: "--primary" },
  pending_review: { label: "Pending review", tone: "--action-investigate" },
  approved: { label: "Approved", tone: "--action-approve" },
  approved_with_deductions: { label: "Approved, deducted", tone: "--action-approve-with-deductions" },
  queried: { label: "Queried", tone: "--action-query" },
  investigating: { label: "Investigating", tone: "--action-refer-siu" },
  rejected: { label: "Rejected", tone: "--action-reject" },
  failed: { label: "Failed", tone: "--destructive" },
};

export function claimStatusLabel(status: string): string {
  return CLAIM_STATUS_META[status as ClaimStatus]?.label ?? humanize(status);
}

/** Claims that can be sent through the pipeline. */
export function isProcessable(status: string): boolean {
  return status === "received" || status === "failed";
}

export const RULE_NAMES: Record<string, string> = {
  R01: "Room rent above cap",
  R02: "ICU rent above cap",
  R03: "Above contracted tariff",
  R04: "Item above MRP",
  R05: "Non-payable item",
  R06: "Waiting period",
  R07: "Sub-limit exceeded",
  R08: "Exact duplicate",
  R09: "Service date outside stay",
  R10: "Exceeds remaining sum insured",
  R11: "Reused document",
};

export function ruleLabel(code: string): string {
  return RULE_NAMES[code] ? `${code} ${RULE_NAMES[code]}` : code;
}

export const PEER_FEATURES = [
  "log_amount",
  "los",
  "cost_per_day",
  "pharmacy_share",
  "room_rent_per_day",
  "final_to_preauth",
  "days_since_policy_start",
] as const;
export type PeerFeature = (typeof PEER_FEATURES)[number];

export const FEATURE_LABELS: Record<string, string> = {
  log_amount: "Claimed amount",
  los: "Length of stay",
  cost_per_day: "Cost per day",
  pharmacy_share: "Pharmacy share",
  room_rent_per_day: "Room rent per day",
  final_to_preauth: "Final bill vs pre-auth",
  days_since_policy_start: "Days since policy start",
  age: "Member age",
  hospital_tier: "Hospital tier",
  city_tier: "City tier",
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? humanize(feature);
}

/** Human value for a model feature. `log_amount` is ln(1 + rupees). */
export function formatFeatureValue(feature: string, value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  switch (feature) {
    case "log_amount": {
      const rupees = Math.expm1(value);
      return compact ? compactRupees(rupees) : formatINR(Math.round(rupees));
    }
    case "cost_per_day":
    case "room_rent_per_day":
      return compact ? compactRupees(value) : formatINR(Math.round(value));
    case "pharmacy_share":
      return formatPercent(value, { digits: compact ? 0 : 1 });
    case "final_to_preauth":
      return `${value.toFixed(2)}×`;
    case "los":
      return `${formatNumber(Math.round(value * 10) / 10)} ${value === 1 ? "day" : "days"}`;
    case "days_since_policy_start":
      return `${formatNumber(Math.round(value))} d`;
    case "age":
      return `${Math.round(value)} y`;
    default:
      return formatNumber(Math.round(value * 100) / 100);
  }
}

function compactRupees(value: number): string {
  if (Math.abs(value) >= 1e7) return `₹${(value / 1e7).toFixed(1).replace(/\.0$/, "")} Cr`;
  if (Math.abs(value) >= 1e5) return `₹${(value / 1e5).toFixed(1).replace(/\.0$/, "")} L`;
  if (Math.abs(value) >= 1e3) return `₹${(value / 1e3).toFixed(0)}K`;
  return `₹${Math.round(value)}`;
}

export const COVERAGE_VERDICTS = ["payable", "not_payable", "partially_payable", "needs_review"] as const;
export type CoverageVerdict = (typeof COVERAGE_VERDICTS)[number];

export const COVERAGE_META: Record<CoverageVerdict, { label: string; tone: string }> = {
  payable: { label: "Payable", tone: "--action-approve" },
  not_payable: { label: "Not payable", tone: "--action-reject" },
  partially_payable: { label: "Partly payable", tone: "--action-approve-with-deductions" },
  needs_review: { label: "Needs review", tone: "--action-investigate" },
};

export const SEVERITY_TONE: Record<string, string> = {
  low: "--risk-low",
  medium: "--risk-medium",
  high: "--risk-high",
  critical: "--risk-high",
};

export const DOC_TYPE_LABELS: Record<string, string> = {
  bill: "Bill",
  discharge_summary: "Discharge summary",
  prescription: "Prescription",
  preauth: "Pre-auth letter",
  other: "Other",
};

export const PARSE_STATUS_META: Record<string, { label: string; tone?: string }> = {
  pending: { label: "Queued" },
  parsing: { label: "Parsing", tone: "--primary" },
  parsed: { label: "Parsed", tone: "--action-approve" },
  needs_human: { label: "Needs review", tone: "--action-investigate" },
  failed: { label: "Failed", tone: "--destructive" },
};

export const CATEGORY_LABELS: Record<string, string> = {
  room: "Room",
  icu: "ICU",
  nursing: "Nursing",
  ot: "OT",
  surgeon: "Surgeon",
  pharmacy: "Pharmacy",
  consumables: "Consumables",
  investigations: "Investigations",
  implants: "Implants",
};

export function humanize(value: string): string {
  const s = value.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Parses a numeric value that may arrive as a decimal string. */
export function num(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export const ROOM_LABELS: Record<string, string> = {
  general: "General ward",
  semi_private: "Semi-private room",
  private: "Private room",
  deluxe: "Deluxe room",
};

export function roomLabel(category: string): string {
  return ROOM_LABELS[category] ?? humanize(category);
}
