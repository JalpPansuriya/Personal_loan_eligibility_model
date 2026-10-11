import { useEffect, useState } from "react";
import { ApplicantInput, Decision, Meta, evaluate, getMeta } from "./api";
import { ageToDob, dobToAge } from "./format";
import ApplicantForm from "./components/ApplicantForm";
import Results from "./components/Results";

const APP_DATE = "2026-01-01";

const DEFAULT_FORM = {
  employment_type: "salaried",
  net_monthly_income: 100000,
  existing_emi_monthly: 15000,
  credit_card_outstanding: 0,
  has_score: true,
  bureau_score: 780,
  age: 32,
  total_experience_months: 120,
  current_job_tenure_months: 60,
  business_vintage_months: 60,
  itr_years_filed: 3,
  itr_income_y1: 1200000,
  employer_category: "private",
  profession: "",
  city: "Mumbai",
  salary_account_with_lender: "none",
  gender: "(not specified)",
  requested_amount: 800000,
  requested_tenure_months: 48,
};

export type FormState = typeof DEFAULT_FORM;

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setError(String(e)));
  }, []);

  // Fill the form from a raw applicant JSON object (e.g. a bundled profile or a
  // pasted payload). Unknown keys are ignored; date_of_birth becomes an age.
  function fillFromJson(obj: Record<string, unknown>): void {
    const f: FormState = { ...DEFAULT_FORM };
    const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
    const str = (v: unknown, d: string) => (typeof v === "string" ? v : d);

    f.employment_type = str(obj.employment_type, f.employment_type);
    f.net_monthly_income = num(obj.net_monthly_income, f.net_monthly_income);
    f.existing_emi_monthly = num(obj.existing_emi_monthly, 0);
    f.credit_card_outstanding = num(obj.credit_card_outstanding, 0);
    if (obj.bureau_score === null) {
      f.has_score = false;
    } else if (typeof obj.bureau_score === "number") {
      f.has_score = true;
      f.bureau_score = obj.bureau_score;
    }
    const appDate = str(obj.application_date, APP_DATE);
    if (typeof obj.date_of_birth === "string") f.age = Math.round(dobToAge(obj.date_of_birth, appDate));
    f.total_experience_months = num(obj.total_experience_months, 0);
    f.current_job_tenure_months = num(obj.current_job_tenure_months, 0);
    f.business_vintage_months = num(obj.business_vintage_months, 0);
    f.itr_years_filed = num(obj.itr_years_filed, 0);
    f.itr_income_y1 = num(obj.itr_income_y1, 0);
    f.employer_category = str(obj.employer_category, f.employer_category);
    f.profession = str(obj.profession, "");
    f.city = str(obj.city, f.city);
    f.salary_account_with_lender = str(obj.salary_account_with_lender, "none") || "none";
    f.gender = str(obj.gender, "(not specified)") || "(not specified)";
    f.requested_amount = num(obj.requested_amount, 0);
    f.requested_tenure_months = num(obj.requested_tenure_months, 0);
    setForm(f);
  }

  function toInput(f: FormState): ApplicantInput {
    const inp: ApplicantInput = {
      employment_type: f.employment_type,
      net_monthly_income: f.net_monthly_income,
      existing_emi_monthly: f.existing_emi_monthly,
      credit_card_outstanding: f.credit_card_outstanding,
      bureau_score: f.has_score ? f.bureau_score : null,
      total_experience_months: f.total_experience_months,
      current_job_tenure_months: f.current_job_tenure_months,
      employer_category: f.employer_category || undefined,
      city: f.city || undefined,
      date_of_birth: ageToDob(f.age, APP_DATE),
      application_date: APP_DATE,
    };
    if (f.salary_account_with_lender !== "none")
      inp.salary_account_with_lender = f.salary_account_with_lender;
    if (f.gender !== "(not specified)") inp.gender = f.gender;
    if (f.requested_amount) inp.requested_amount = f.requested_amount;
    if (f.requested_tenure_months) inp.requested_tenure_months = f.requested_tenure_months;
    if (f.profession) inp.profession = f.profession;
    if (f.employment_type !== "salaried") {
      inp.business_vintage_months = f.business_vintage_months;
      inp.itr_years_filed = f.itr_years_filed;
      if (f.itr_income_y1) inp.itr_income_y1 = f.itr_income_y1;
    }
    return inp;
  }

  async function onSubmit() {
    setLoading(true);
    setError(null);
    try {
      const d = await evaluate(toInput(form));
      setDecision(d);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setDecision(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="layout">
      <header>
        <h1>Personal Loan Eligibility</h1>
        <p className="subtitle">
          Rule-based engine over the published criteria of India&rsquo;s 20 largest personal-loan
          lenders. Rates include processing fee + 18% GST. Not a loan offer.
        </p>
      </header>

      <section className="form-pane">
        {meta ? (
          <ApplicantForm
            meta={meta}
            form={form}
            setForm={setForm}
            onSubmit={onSubmit}
            loading={loading}
            onFillJson={fillFromJson}
          />
        ) : (
          <p>Loading form&hellip;</p>
        )}
      </section>

      <section className="results-pane">
        {error && <div className="error">{error}</div>}
        {!decision && !error && <p className="hint">Fill the form and click <b>Check eligibility</b>.</p>}
        {decision && <Results decision={decision} />}
      </section>
    </div>
  );
}
