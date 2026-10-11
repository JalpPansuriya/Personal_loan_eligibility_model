// Pure, side-effect-free mapping between raw applicant JSON, the form state, and the
// backend ApplicantInput. Kept separate from React so it can be unit-tested (vitest) and
// so the data-mapping defects (A-E) are covered by a direct test of these functions.
//
// Rules (plan2 §3):
//   * canonical field names are plan2's; legacy names are accepted as aliases;
//   * dates are preserved verbatim (no age<->dob round trip, no app-date substitution);
//   * missing financially-material values stay UNDEFINED (null), never silently 0.

import { ApplicantInput } from "./api";

export const APP_DATE_FALLBACK = "2026-10-11";

export interface FormState {
  employment_type: string;
  net_monthly_income: number;
  gross_monthly_income: number | null;
  existing_monthly_emi: number | null;
  card_outstanding: number | null;
  card_monthly_payment: number | null;
  has_credit_score: boolean | null;
  bureau_score: number | null;
  max_dpd_days_last_12_months: number | null;
  enquiries_last_6_months: number | null;
  has_settled_loan: boolean;
  settled_loan_months_ago: number | null;
  write_off_flag: boolean;
  total_experience_months: number | null;
  current_job_tenure_months: number | null;
  business_vintage_months: number | null;
  itr_years_available: number | null;
  itr_income_y1: number | null;
  verified_annual_income: number | null;
  employer_category: string;
  employer_check_off_available: boolean | null;
  profession: string;
  city: string;
  salary_account_with: string;
  gender: string;
  requested_amount: number | null;
  requested_tenure_months: number | null;
  date_of_birth: string;
  application_date: string;
}

export const EMPTY_FORM: FormState = {
  employment_type: "salaried",
  net_monthly_income: 100000,
  gross_monthly_income: null,
  existing_monthly_emi: null,
  card_outstanding: null,
  card_monthly_payment: null,
  has_credit_score: true,
  bureau_score: 780,
  max_dpd_days_last_12_months: null,
  enquiries_last_6_months: null,
  has_settled_loan: false,
  settled_loan_months_ago: null,
  write_off_flag: false,
  total_experience_months: null,
  current_job_tenure_months: null,
  business_vintage_months: null,
  itr_years_available: null,
  itr_income_y1: null,
  verified_annual_income: null,
  employer_category: "",
  employer_check_off_available: null,
  profession: "",
  city: "",
  salary_account_with: "none",
  gender: "(not specified)",
  requested_amount: null,
  requested_tenure_months: null,
  date_of_birth: "1994-01-01",
  application_date: APP_DATE_FALLBACK,
};

// accept both canonical and legacy aliases from a raw payload
const ALIASES: Record<string, string> = {
  existing_emi_monthly: "existing_monthly_emi",
  credit_card_outstanding: "card_outstanding",
  salary_account_with_lender: "salary_account_with",
  max_dpd_last_12m: "max_dpd_days_last_12_months",
  enquiries_last_6m: "enquiries_last_6_months",
  itr_years_filed: "itr_years_available",
  writeoff_or_settled_24m: "write_off_flag",
};

const KNOWN = new Set<string>([
  "profile_id", "description", "employment_type", "net_monthly_income", "gross_monthly_income",
  "existing_monthly_emi", "card_outstanding", "card_monthly_payment", "has_credit_score", "bureau_score",
  "max_dpd_days_last_12_months", "enquiries_last_6_months", "has_settled_loan",
  "settled_loan_months_ago", "write_off_flag", "total_experience_months",
  "current_job_tenure_months", "business_vintage_months", "itr_years_available",
  "itr_income_y1", "verified_annual_income", "employer_category", "employer_check_off_available",
  "profession", "city", "salary_account_with",
  "gender", "requested_amount", "requested_tenure_months", "date_of_birth",
  "application_date", ...Object.keys(ALIASES),
]);

export function unknownKeys(obj: Record<string, unknown>): string[] {
  return Object.keys(obj).filter((k) => !KNOWN.has(k));
}

function canonicalise(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    out[ALIASES[k] ?? k] = v;
  }
  return out;
}

// Fill a FormState from a raw profile object. Missing values become null (not 0); dates
// are kept exactly; employment aliases are normalised by the backend, so pass through.
export function formFromJson(raw: Record<string, unknown>): FormState {
  const o = canonicalise(raw);
  const num = (v: unknown): number | null => (typeof v === "number" ? v : null);
  const str = (v: unknown, d: string): string => (typeof v === "string" ? v : d);
  const bool = (v: unknown, d: boolean | null): boolean | null =>
    (typeof v === "boolean" ? v : d);

  return {
    employment_type: str(o.employment_type, EMPTY_FORM.employment_type),
    net_monthly_income: num(o.net_monthly_income) ?? EMPTY_FORM.net_monthly_income,
    gross_monthly_income: num(o.gross_monthly_income),
    existing_monthly_emi: num(o.existing_monthly_emi),
    card_outstanding: num(o.card_outstanding),
    card_monthly_payment: num(o.card_monthly_payment),
    has_credit_score:
      o.has_credit_score === undefined
        ? (o.bureau_score === null ? false : o.bureau_score !== undefined ? true : null)
        : bool(o.has_credit_score, null),
    bureau_score: num(o.bureau_score),
    max_dpd_days_last_12_months: num(o.max_dpd_days_last_12_months),
    enquiries_last_6_months: num(o.enquiries_last_6_months),
    has_settled_loan: bool(o.has_settled_loan, false) as boolean,
    settled_loan_months_ago: num(o.settled_loan_months_ago),
    write_off_flag: bool(o.write_off_flag, false) as boolean,
    total_experience_months: num(o.total_experience_months),
    current_job_tenure_months: num(o.current_job_tenure_months),
    business_vintage_months: num(o.business_vintage_months),
    itr_years_available: num(o.itr_years_available),
    itr_income_y1: num(o.itr_income_y1),
    verified_annual_income: num(o.verified_annual_income),
    employer_category: str(o.employer_category, ""),
    employer_check_off_available: bool(o.employer_check_off_available, null),
    profession: str(o.profession, ""),
    city: str(o.city, ""),
    salary_account_with: str(o.salary_account_with, "none") || "none",
    gender: str(o.gender, "(not specified)") || "(not specified)",
    requested_amount: num(o.requested_amount),
    requested_tenure_months: num(o.requested_tenure_months),
    date_of_birth: str(o.date_of_birth, EMPTY_FORM.date_of_birth),
    application_date: str(o.application_date, APP_DATE_FALLBACK),
  };
}

// Build the backend payload. Only send fields the user actually provided; never coerce a
// blank into 0. The self-employed-only fields are included only for SE applicants.
export function toInput(f: FormState): ApplicantInput {
  const inp: ApplicantInput = {
    employment_type: f.employment_type,
    net_monthly_income: f.net_monthly_income,
    date_of_birth: f.date_of_birth,
    application_date: f.application_date,
  };
  const put = <K extends keyof ApplicantInput>(k: K, v: ApplicantInput[K] | null) => {
    if (v !== null && v !== undefined && v !== "") (inp[k] as unknown) = v;
  };
  put("existing_monthly_emi", f.existing_monthly_emi);
  put("gross_monthly_income", f.gross_monthly_income);
  put("card_outstanding", f.card_outstanding);
  if (f.card_outstanding && f.card_monthly_payment !== null) put("card_monthly_payment", f.card_monthly_payment);
  if (f.has_credit_score === false) {
    inp.has_credit_score = false;
  } else if (f.has_credit_score === true) {
    inp.has_credit_score = true;
    put("bureau_score", f.bureau_score);
  }
  put("max_dpd_days_last_12_months", f.max_dpd_days_last_12_months);
  put("enquiries_last_6_months", f.enquiries_last_6_months);
  if (f.has_settled_loan) {
    inp.has_settled_loan = true;
    put("settled_loan_months_ago", f.settled_loan_months_ago);
  }
  if (f.write_off_flag) inp.write_off_flag = true;
  put("total_experience_months", f.total_experience_months);
  put("current_job_tenure_months", f.current_job_tenure_months);
  put("employer_category", f.employer_category || null);
  if (f.employer_check_off_available !== null) inp.employer_check_off_available = f.employer_check_off_available;
  put("city", f.city || null);
  if (f.salary_account_with !== "none") inp.salary_account_with = f.salary_account_with;
  if (f.gender !== "(not specified)") inp.gender = f.gender;
  put("requested_amount", f.requested_amount);
  put("requested_tenure_months", f.requested_tenure_months);
  if (f.profession) inp.profession = f.profession;
  if (f.employment_type !== "salaried") {
    put("business_vintage_months", f.business_vintage_months);
    put("itr_years_available", f.itr_years_available);
    put("itr_income_y1", f.itr_income_y1);
    put("verified_annual_income", f.verified_annual_income);
  }
  return inp;
}
