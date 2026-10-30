/**
 * Display formatting for rule-finding evidence (backend/app/services/rules/checks/*).
 * Evidence is a flat dict of decimal strings plus a few nested lists; keys decide the format.
 */
import { formatDate, formatINR, formatNumber, formatPercent } from "./format";
import { CATEGORY_LABELS, humanize } from "./labels";

const LABELS: Record<string, string> = {
  cap_pct_of_si: "Cap % of sum insured",
  icu_cap_pct_of_si: "ICU cap % of sum insured",
  cap_per_day: "Cap per day",
  room_rent_per_day: "Room rent per day",
  icu_rent_per_day: "ICU rent per day",
  excess_rent: "Excess rent",
  proportional_deduction: "Proportional deduction",
  sum_insured: "Sum insured",
  remaining_sum_insured: "Remaining sum insured",
  package_rate: "Contracted package rate",
  procedure_charges: "Procedure charges billed",
  procedure_code: "Procedure",
  eligible_before_limit: "Eligible before limit",
  payable_before_cap: "Payable before cap",
  sub_limit: "Sub-limit",
  mrp: "MRP",
  unit_price: "Unit price",
  qty: "Quantity",
  days: "Days",
  ratio: "Cap to rent ratio",
  admission_at: "Admitted",
  discharge_at: "Discharged",
  service_date: "Service date",
  duplicate_of: "Duplicate of",
  description: "Item",
  associated: "Associated charges scaled down",
  lines: "Procedure lines",
  waiting_days: "Waiting period",
  days_since_start: "Days since policy start",
};

const MONEY_KEYS = new Set([
  "sum_insured",
  "cap_per_day",
  "room_rent_per_day",
  "icu_rent_per_day",
  "package_rate",
  "procedure_charges",
  "mrp",
  "unit_price",
  "sub_limit",
  "eligible_before_limit",
  "remaining_sum_insured",
  "payable_before_cap",
  "excess_rent",
  "amount",
  "deduction",
  "excess",
]);
const MONEY_SUFFIXES = ["_amount", "_rent", "_deduction", "_price", "_charges", "_limit"];
const DATE_KEYS = /(_at|_date)$/;
const HIDDEN_KEYS = new Set(["line_item_id"]);

export function evidenceLabel(key: string): string {
  return LABELS[key] ?? humanize(key);
}

export function isMoneyKey(key: string): boolean {
  return MONEY_KEYS.has(key) || MONEY_SUFFIXES.some((s) => key.endsWith(s));
}

const NUMERIC = /^-?\d+(\.\d+)?$/;

function trimNumber(value: string | number): string {
  const n = Number(value);
  return Number.isInteger(n) ? formatNumber(n) : formatNumber(Math.round(n * 100) / 100);
}

/** Formats one scalar evidence value by its key. */
export function formatEvidenceValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "–";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map((v) => formatEvidenceValue(key, v)).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  const s = String(value);
  const numeric = NUMERIC.test(s);
  if (numeric && (key.endsWith("_pct") || key.endsWith("_pct_of_si"))) {
    return `${trimNumber(s)}%${key.endsWith("_of_si") ? " of SI" : ""}`;
  }
  if (numeric && key === "ratio") return formatPercent(Number(s));
  if (numeric && isMoneyKey(key)) return formatINR(s);
  if (numeric && (key === "qty" || key.endsWith("days") || key === "days")) {
    const n = Number(s);
    return `${trimNumber(n)}${key.endsWith("days") ? (n === 1 ? " day" : " days") : ""}`;
  }
  if (DATE_KEYS.test(key) && /^\d{4}-\d{2}-\d{2}/.test(s)) return formatDate(s);
  if (numeric) return trimNumber(s);
  return s;
}

export interface EvidenceRow {
  key: string;
  label: string;
  value: string;
}

export interface EvidenceList {
  key: string;
  label: string;
  rows: { label: string; amount: string; deduction: string | null }[];
}

/** Splits evidence into scalar facts and nested line lists, formatted for display. */
export function formatEvidence(evidence: Record<string, unknown>): { facts: EvidenceRow[]; lists: EvidenceList[] } {
  const facts: EvidenceRow[] = [];
  const lists: EvidenceList[] = [];
  for (const [key, value] of Object.entries(evidence)) {
    if (HIDDEN_KEYS.has(key) || value === null || value === undefined) continue;
    if (Array.isArray(value) && value.some((v) => v && typeof v === "object")) {
      lists.push({
        key,
        label: evidenceLabel(key),
        rows: value
          .filter((v): v is Record<string, unknown> => !!v && typeof v === "object")
          .map((v) => {
            const category = typeof v.category === "string" ? v.category : null;
            const label =
              (category && (CATEGORY_LABELS[category] ?? humanize(category))) ??
              (typeof v.description === "string" ? v.description : `Line ${v.line_item_id ?? ""}`.trim());
            return {
              label,
              amount: formatEvidenceValue("amount", v.amount),
              deduction: v.deduction !== undefined && v.deduction !== null ? formatEvidenceValue("deduction", v.deduction) : null,
            };
          }),
      });
      continue;
    }
    if (typeof value === "object" && !Array.isArray(value)) continue;
    facts.push({ key, label: evidenceLabel(key), value: formatEvidenceValue(key, value) });
  }
  return { facts, lists };
}
