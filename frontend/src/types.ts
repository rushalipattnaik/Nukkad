// Mirrors backend/app/domain/schemas.py - no codegen here, so keep both
// in sync by hand if you change one.

export type GapType = "ABSENCE" | "QUALITY" | "SERVICE_WINDOW";
export type ConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";
export type ClaimType = "FACT" | "COMPUTED" | "INTERPRETATION" | "UNCERTAIN";
export type ScanPreset = "lite" | "standard" | "deep";
export type EvidenceKind =
  | "PLACE" | "REVIEW" | "REVIEW_TOPIC" | "TREND_SERIES" | "TREND_REGION"
  | "RELATED_QUERY" | "SUGGESTION" | "NEWS_ITEM" | "COMPUTED";

export interface Claim {
  claim_type: ClaimType;
  text: string;
  evidence_ids: string[];
  verified: boolean;
  drop_reason?: string | null;
}

export interface ConflictFlag {
  rule_id: string;
  label: string;
  explanation: string;
  confidence_delta: number;
  validate_next: string[];
}

export interface Gap {
  gap_id: string;
  category: string;
  gap_type: GapType;
  strength: number;
  confidence: ConfidenceLevel;
  confidence_reasons: string[];
  missing_information: string[];
  what_exists: Claim[];
  what_customers_say: Claim[];
  what_people_search: Claim[];
  what_is_changing: Claim[];
  why_we_think_this: Claim[];
  conflicts: ConflictFlag[];
  validate_next: string[];
  dropped_claim_count: number;
}

export interface CategoryResult {
  category: string;
  supply_count: number;
  supply_within_radius: number;
  mean_rating: number | null;
  low_rating_share: number | null;
  hours_coverage_pct: number | null;
  open_in_need_window_share: number | null;
  demand_label: string | null;
  demand_is_regional: boolean;
  prelim_score: number;
  selected_for_deep: boolean;
  evidence_ids: string[];
}

export interface EvidenceItem {
  evidence_id: string;
  scan_id: string;
  kind: EvidenceKind;
  engine: string;
  query: Record<string, unknown>;
  retrieved_at: string;
  cache_hit: boolean;
  title: string;
  data: Record<string, unknown>;
  source_ref: string | null;
  category: string | null;
  lat: number | null;
  lng: number | null;
  derived_from: string[];
}

export interface BudgetLine {
  label: string;
  planned_calls: number;
  used_calls: number;
}

export interface BudgetStatus {
  cap: number;
  counted_spent: number;
  measured_spent: number | null;
  cache_hits: number;
  lines: BudgetLine[];
  refused_calls: number;
}

export interface TimelineStep {
  phase: string;
  label: string;
  detail?: string;
  engine?: string | null;
  query?: Record<string, unknown> | null;
  result_count?: number | null;
  status: "ok" | "empty" | "error" | "budget_exceeded";
  seq: number;
}

export interface ScanResult {
  scan_id: string;
  town_name: string;
  center_lat: number;
  center_lng: number;
  radius_km: number;
  preset: ScanPreset;
  mode: string;
  status: "completed" | "failed";
  created_at: string;
  budget: BudgetStatus;
  timeline: TimelineStep[];
  category_results: CategoryResult[];
  gaps: Gap[];
  evidence: Record<string, EvidenceItem>;
  warnings: string[];
  llm_used: boolean;
  llm_model: string | null;
}

export interface ScanRequestBody {
  town_name: string;
  radius_km: number;
  preset: ScanPreset;
  categories?: string[] | null;
  center_lat?: number | null;
  center_lng?: number | null;
  mode?: "live" | "snapshot";
}

export interface ScanListItem {
  scan_id: string;
  town_name: string;
  preset: string;
  status: string;
  created_at: string;
}
