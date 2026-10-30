/**
 * Response shapes for endpoints the backend returns as untyped dicts (FastAPI emits
 * `{ [key: string]: unknown }` for them in OpenAPI). Kept in one place and checked against
 * backend/app/api/*.py. Money is always a decimal string.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type Money = string;

export type ClaimListItem = S["ClaimListItem"];
export type ClaimDetail = S["ClaimDetail"];
export type LineItem = S["LineItemOut"];
export type RuleFinding = S["RuleFindingOut"];
export type CoverageFinding = S["CoverageFindingOut"];
export type ClaimDocument = S["DocumentOut"];
export type Recommendation = S["RecommendationOut"];
export type Anomaly = S["AnomalyOut"];
export type Review = S["ReviewOut"];

export interface Page<T> {
  items: T[];
  total: number;
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface Job {
  id: number;
  type: string;
  status: JobStatus;
  result: unknown;
  error: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ClaimMember {
  id: string;
  name: string;
  age: number;
  gender: string;
  city: string;
  member_since: string;
  declared_conditions: string[] | null;
}

export interface ClaimPolicy {
  id: string;
  product_id: string;
  sum_insured: Money;
  balance: Money;
  start_date: string;
  end_date: string;
}

export interface ClaimProvider {
  id: string;
  name: string;
  city: string;
  city_tier: number;
  hospital_tier: number;
  nabh: boolean;
  network: boolean;
}

export interface PayableStep {
  step: number;
  name: string;
  rule_codes?: string[];
  before: Money;
  after: Money;
  delta: Money;
  detail?: string;
}

export interface FeatureZ {
  value: number;
  median: number | null;
  rz: number;
  one_sided: number;
  level: number | null;
  n: number;
}

export interface ShapContributor {
  feature: string;
  label: string;
  value: number;
  display_value: string;
  shap: number;
}

export interface AnomalyReason {
  source: "robust_z" | "isolation_forest" | string;
  feature: string;
  text: string;
  z?: number;
  shap?: number;
}

export interface InvestigationReport {
  summary: string;
  findings: { statement: string; evidence_tool: string; evidence: string }[];
  suggested_action?: string;
  open_questions?: string[];
  incomplete?: boolean;
  [key: string]: unknown;
}

export interface PeerDistribution {
  feature: string;
  label: string;
  level: number;
  group: Record<string, string | number>;
  n: number;
  claim_value: number;
  quantiles: Partial<Record<"p10" | "p50" | "p90" | "p99", number>>;
  percentile: number | null;
  values: number[];
}

export interface AuditEntry {
  id: number;
  actor_type: string;
  actor_id: string;
  actor_name: string | null;
  action: string;
  entity: string;
  entity_id: string;
  payload: Record<string, unknown> | null;
  model: string | null;
  created_at: string;
}

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ClauseText {
  clause_no: string;
  section_path: string | null;
  page: number | null;
  text: string;
}

export interface DashboardSummary {
  kpis: {
    processed: number;
    leakage_identified: Money;
    claimed_processed: Money;
    payable_processed: Money;
    auto_approval_rate: number | string;
    pending_review: number;
    total_claims: number;
    unprocessed: number;
  };
  leakage_by_rule: { rule_code: string; findings: number; amount: Money }[];
  by_action: { action: string; claims: number; leakage: Money | null }[];
  weekly: { week: string; claims: number; leakage: Money | null; claimed: Money | null; auto_approval_rate: number | string }[];
  leakage_by_provider: { provider_id: string; name: string; claims: number; leakage: Money | null }[];
  leakage_by_procedure: { procedure_code: string; name: string; claims: number; leakage: Money | null }[];
  risk_tiers: { tier: string; claims: number }[];
}

export interface ProviderRow {
  rank: number;
  id: string;
  name: string;
  city: string;
  city_tier: number;
  hospital_tier: number;
  nabh: boolean;
  network: boolean;
  claims: number;
  claimed_total: Money | null;
  leakage_total: Money | null;
  flag_rate: number | string | null;
  oe_index: number | string | null;
  oe_index_weighted: number | string | null;
  avg_pharmacy_share: number | string | null;
  peer_pharmacy_share: number | string | null;
}

export interface ProviderProfile {
  provider: {
    id: string;
    name: string;
    city: string;
    city_tier: number;
    hospital_tier: number;
    nabh: boolean;
    beds: number | null;
    network: boolean;
    joined_at: string | null;
  };
  summary: ProviderRow | null;
  trend: {
    period: string;
    claims: number;
    claimed_total: Money | null;
    leakage_total: Money | null;
    flag_rate: number | string | null;
    oe_index: number | string | null;
    avg_pharmacy_share: number | string | null;
    peer_pharmacy_share: number | string | null;
  }[];
  common_findings: { rule_code: string; rule_name: string; findings: number; amount: Money | null }[];
  top_procedures: { procedure_code: string; name: string; claims: number; avg_claimed: Money | null }[];
}

export interface PolicyParams {
  room_rent_cap_pct: number | string | null;
  icu_cap_pct: number | string | null;
  copay_pct: number | string | null;
  deductible: Money | number | null;
  sub_limits: Record<string, Money | number> | null;
  initial_days: number | null;
  listed_conditions_months: number | null;
  pre_existing_months: number | null;
  clause_refs: Record<string, string> | null;
}

export interface PolicyProduct {
  id: string;
  name: string;
  version: string | number | null;
  status: string | null;
  has_wording: boolean;
  chunks: number;
  params: PolicyParams | null;
  approved_by: string | null;
  approved_at: string | null;
  proposed: Record<string, unknown> | null;
  diff: { param: string; current: unknown; proposed: unknown; changed: boolean }[];
}

export interface PolicyChunk {
  id: number;
  clause_no: string | null;
  section_path: string | null;
  clause_type: string | null;
  page: number | null;
  text: string;
}

export interface PolicySearchResult extends PolicyChunk {
  score: number;
  vector_rank: number | null;
  keyword_rank: number | null;
  definitions?: PolicyChunk[];
}

export interface ScenarioMetrics {
  precision_at_50?: number;
  precision_at_100?: number;
  flagged?: number;
  recall?: Record<string, number>;
}

export interface ModelMetrics {
  version?: string;
  n_claims?: number;
  n_positive?: number;
  threshold?: number;
  z_only?: ScenarioMetrics;
  iforest_only?: ScenarioMetrics;
  combined?: ScenarioMetrics;
  overbilling_providers?: {
    providers?: number | string[];
    share_of_top100?: number;
    share_of_all?: number;
    lift?: number;
  };
  [key: string]: unknown;
}

export interface ModelEntry {
  version: string;
  kind: string;
  trained_at: string;
  active: boolean;
  metrics: ModelMetrics | null;
}

export interface AdminJob extends Job {
  payload?: unknown;
}
