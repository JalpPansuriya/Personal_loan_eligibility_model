import { describe, it, expect } from "vitest";
import { formFromJson, toInput, unknownKeys } from "./mapping";

// EDGE profiles mirror the Python fixtures; the mapping must preserve every material value.
const EDGE02 = {
  profile_id: "EDGE02",
  date_of_birth: "1992-06-10",
  application_date: "2026-10-11",
  employment_type: "salaried",
  net_monthly_income: 120000,
  existing_monthly_emi: 10000,
  card_outstanding: 300000,
  has_credit_score: true,
  bureau_score: 640,
  max_dpd_days_last_12_months: 60,
  enquiries_last_6_months: 9,
  total_experience_months: 96,
  current_job_tenure_months: 48,
  employer_category: "mnc",
  city: "Mumbai",
  salary_account_with: "hdfc",
  requested_amount: 500000,
  requested_tenure_months: 36,
};

describe("formFromJson preserves material values (defects A-E)", () => {
  it("keeps EMI, card outstanding and salary account (A/B)", () => {
    const f = formFromJson(EDGE02);
    expect(f.existing_monthly_emi).toBe(10000);
    expect(f.card_outstanding).toBe(300000);
    expect(f.salary_account_with).toBe("hdfc");
  });

  it("keeps employment tenure (C)", () => {
    const f = formFromJson({ ...EDGE02, current_job_tenure_months: 4, total_experience_months: 36 });
    expect(f.current_job_tenure_months).toBe(4);
    expect(f.total_experience_months).toBe(36);
  });

  it("preserves dates exactly (D)", () => {
    const f = formFromJson(EDGE02);
    expect(f.date_of_birth).toBe("1992-06-10");
    expect(f.application_date).toBe("2026-10-11");
  });

  it("leaves missing ITR as null, never 0 (E)", () => {
    const f = formFromJson(EDGE02);
    expect(f.itr_years_available).toBeNull();
  });

  it("accepts legacy aliases", () => {
    const f = formFromJson({ ...EDGE02, existing_emi_monthly: 7777, card_outstanding: undefined,
      credit_card_outstanding: 8888, salary_account_with: undefined, salary_account_with_lender: "icici" });
    expect(f.existing_monthly_emi).toBe(7777);
    expect(f.card_outstanding).toBe(8888);
    expect(f.salary_account_with).toBe("icici");
  });
});

describe("toInput round-trip", () => {
  it("sends canonical names and the exact request", () => {
    const inp = toInput(formFromJson(EDGE02));
    expect(inp.existing_monthly_emi).toBe(10000);
    expect(inp.card_outstanding).toBe(300000);
    expect(inp.salary_account_with).toBe("hdfc");
    expect(inp.requested_amount).toBe(500000);
    expect(inp.requested_tenure_months).toBe(36);
    expect(inp.date_of_birth).toBe("1992-06-10");
    expect(inp.application_date).toBe("2026-10-11");
  });

  it("omits blank optionals instead of zero-filling", () => {
    const f = formFromJson({ employment_type: "salaried", net_monthly_income: 50000,
      date_of_birth: "1995-01-01", application_date: "2026-10-11" });
    const inp = toInput(f);
    expect(inp.existing_monthly_emi).toBeUndefined();
    expect(inp.card_outstanding).toBeUndefined();
    expect("itr_years_available" in inp).toBe(false);
  });

  it("marks NTC via has_credit_score=false, no score", () => {
    const inp = toInput(formFromJson({ employment_type: "salaried", net_monthly_income: 30000,
      has_credit_score: false, bureau_score: null, date_of_birth: "2005-07-15",
      application_date: "2026-10-11" }));
    expect(inp.has_credit_score).toBe(false);
    expect(inp.bureau_score).toBeUndefined();
  });
});

describe("unknownKeys", () => {
  it("flags unsupported keys", () => {
    expect(unknownKeys({ net_monthly_income: 1, annual_bonus: 2 })).toContain("annual_bonus");
  });
  it("accepts all known + alias keys", () => {
    expect(unknownKeys(EDGE02)).toEqual([]);
  });
  it("accepts the new plan3 fields", () => {
    expect(unknownKeys({ card_monthly_payment: 2000, employer_check_off_available: true,
      verified_annual_income: 1200000, gross_monthly_income: 150000 })).toEqual([]);
  });
});

describe("plan3 fields (Case C/D)", () => {
  it("sends card_monthly_payment only with a balance", () => {
    const withPay = toInput(formFromJson({ ...EDGE02, card_monthly_payment: 2500 }));
    expect(withPay.card_monthly_payment).toBe(2500);
    const noBalance = toInput(formFromJson({ employment_type: "salaried", net_monthly_income: 50000,
      card_outstanding: 0, card_monthly_payment: 2500, date_of_birth: "1995-01-01",
      application_date: "2026-10-11" }));
    expect("card_monthly_payment" in noBalance).toBe(false);
  });
  it("leaves card_monthly_payment null when balance present but payment absent", () => {
    const f = formFromJson(EDGE02);  // card 300000, no payment
    expect(f.card_monthly_payment).toBeNull();
    expect("card_monthly_payment" in toInput(f)).toBe(false);
  });
  it("passes gross income and check-off through", () => {
    const inp = toInput(formFromJson({ ...EDGE02, gross_monthly_income: 160000,
      employer_check_off_available: true }));
    expect(inp.gross_monthly_income).toBe(160000);
    expect(inp.employer_check_off_available).toBe(true);
  });
});
