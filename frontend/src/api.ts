// Types mirroring the FastAPI responses (src/eligibility/api.py + schema.py).

export interface Meta {
  lenders: { id: string; type: string }[];
  employment_types: string[];
  genders: string[];
  residence_types: string[];
  marital_statuses: string[];
  salary_account_options: string[];
  tenures: number[];
  employer_categories: string[];
}

export interface ReasonCode {
  code: string;
  variable: string;
  message: string;
  rule_id: string;
  applicant_value: string | null;
  required_value: string | null;
  rule_status: string;
  confidence: string | null;
  source_url: string;
  next_action: string;
}

export interface Fix {
  lever: string;
  description: string;
  amount: number | null;
  unit: string;
}

export interface AmountQuote {
  amount: number | null;
  tenure_months: number | null;
  emi: number | null;
}

export interface CapBreakdown {
  foir: number | null;
  take_home: number | null;
  multiple: number | null;
  product: number | null;
  calculator: number | null;
  binding_cap: string;
}

export interface PricingBreakdown {
  nominal_rate_pa: number | null;
  rate_is_range: boolean;
  rate_min_pa: number | null;
  rate_max_pa: number | null;
  rate_source: string;
  rate_confidence: string | null;
  rate_source_url: string;
  rate_accessed_date: string;
  processing_fee: number | null;
  gst_on_fee: number | null;
  other_charges: number | null;
  net_disbursement: number | null;
  total_repayment: number | null;
  total_cost_of_credit: number | null;
  apr_pa: number | null;
  apr_available: boolean;
  apr_note: string;
}

export type Status =
  | "ELIGIBLE_TO_QUERY_LENDERS"
  | "PRELIMINARILY_ELIGIBLE"
  | "NOT_ELIGIBLE"
  | "ADDITIONAL_INFORMATION_REQUIRED"
  | "MANUAL_REVIEW"
  | "INVALID_INPUT"
  | "RULES_UNAVAILABLE";

export interface LenderOffer {
  lender_id: string;
  product: string;
  product_label: string;
  segment: string;
  status: Status;
  requested: AmountQuote;
  max_eligible: AmountQuote;
  requested_supported: boolean;
  caps: CapBreakdown;
  pricing: PricingBreakdown;
  strength_score: number | null;
  reasons: ReasonCode[];
  fixes: Fix[];
  rationale: string;
  lowest_confidence: string | null;
}

export interface Decision {
  eligible: boolean;
  offers: LenderOffer[];
  best_offer: LenderOffer | null;
  best_rationale: string;
  top_blocking_reasons: ReasonCode[];
  applicant_age: number;
  disclaimer: string;
}

export interface ModelSummary {
  lenders_configured: number;
  products_configured: number;
  products_with_published_rules: number;
  products_mostly_estimated: number;
  products_apr_reliable: number;
  rules_total: number;
  rules_by_confidence: Record<string, number>;
  note: string;
}

// The applicant form payload. Optional fields are omitted when empty.
export interface ApplicantInput {
  employment_type: string;
  net_monthly_income: number;
  existing_emi_monthly?: number;
  credit_card_outstanding?: number;
  bureau_score?: number | null;
  total_experience_months?: number;
  current_job_tenure_months?: number;
  business_vintage_months?: number | null;
  itr_years_filed?: number;
  itr_income_y1?: number | null;
  employer_category?: string;
  profession?: string;
  city?: string;
  salary_account_with_lender?: string | null;
  gender?: string | null;
  requested_amount?: number | null;
  requested_tenure_months?: number | null;
  date_of_birth: string;
  application_date: string;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export async function getMeta(): Promise<Meta> {
  const r = await fetch("/api/meta");
  if (!r.ok) throw new Error("failed to load metadata");
  return r.json();
}

export async function getProfiles(): Promise<Record<string, unknown>[]> {
  const r = await fetch("/api/profiles");
  if (!r.ok) throw new Error("failed to load profiles");
  return r.json();
}

export async function getSummary(): Promise<ModelSummary> {
  const r = await fetch("/api/summary");
  if (!r.ok) throw new Error("failed to load summary");
  return r.json();
}

export async function evaluate(input: ApplicantInput): Promise<Decision> {
  const r = await fetch("/api/evaluate", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
  if (r.status === 422) {
    const body = await r.json();
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
      : body.detail;
    throw new Error(`Invalid input: ${detail}`);
  }
  if (!r.ok) throw new Error("evaluation failed");
  return r.json();
}
