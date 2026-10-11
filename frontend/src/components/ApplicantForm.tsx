import { useState } from "react";
import { Meta, getProfiles } from "../api";
import { FormState } from "../mapping";

interface Props {
  meta: Meta;
  form: FormState;
  setForm: (f: FormState) => void;
  onSubmit: () => void;
  loading: boolean;
  onFillJson: (obj: Record<string, unknown>) => void;
}

export default function ApplicantForm({ meta, form, setForm, onSubmit, loading, onFillJson }: Props) {
  const up = (patch: Partial<FormState>) => setForm({ ...form, ...patch });
  // blank input -> null (preserve "unknown"); a typed number -> that number
  const onum = (v: string): number | null => (v === "" ? null : Number(v));
  const isSE = form.employment_type !== "salaried";

  const [jsonText, setJsonText] = useState("");
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Record<string, unknown>[]>([]);

  function applyJson() {
    try {
      const obj = JSON.parse(jsonText);
      if (typeof obj !== "object" || obj === null) throw new Error("not an object");
      onFillJson(obj as Record<string, unknown>);
      setJsonErr(null);
    } catch (e) {
      setJsonErr("Invalid JSON: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function loadProfiles() {
    if (profiles.length === 0) {
      try {
        setProfiles(await getProfiles());
      } catch {
        setJsonErr("could not load sample profiles");
      }
    }
  }

  const numVal = (v: number | null) => (v === null ? "" : String(v));

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <div className="form-head"><h2>Applicant</h2></div>

      <details className="json-box" onToggle={(e) => (e.target as HTMLDetailsElement).open && loadProfiles()}>
        <summary>Paste JSON / load a sample profile (auto-fills the form)</summary>
        <div className="json-actions">
          <select
            defaultValue=""
            onChange={(e) => {
              const p = profiles.find((x) => x.profile_id === e.target.value);
              if (p) { setJsonText(JSON.stringify(p, null, 2)); onFillJson(p); }
            }}
          >
            <option value="">— pick a sample profile —</option>
            {profiles.map((p) => (
              <option key={String(p.profile_id)} value={String(p.profile_id)}>
                {String(p.profile_id)} — {String(p.description ?? "")}
              </option>
            ))}
          </select>
        </div>
        <textarea
          rows={6}
          placeholder='{"employment_type":"salaried","net_monthly_income":90000,"bureau_score":770,"date_of_birth":"1994-01-01","application_date":"2026-10-11"}'
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
        />
        <div className="json-actions">
          <button type="button" className="secondary" onClick={applyJson}>Fill form from JSON</button>
          <span className="json-note">Unsupported keys are reported, not dropped. Dates are preserved exactly.</span>
        </div>
        {jsonErr && <div className="json-err">{jsonErr}</div>}
      </details>

      <div className="fields">
        <label>
          Employment type
          <select value={form.employment_type} onChange={(e) => up({ employment_type: e.target.value })}>
            {meta.employment_types.map((t) => (
              <option key={t} value={t}>
                {t === "salaried" ? "Salaried" : t === "sep" ? "Self-employed professional" : "Self-employed business"}
              </option>
            ))}
          </select>
        </label>

        <label>Date of birth
          <input type="date" value={form.date_of_birth}
            onChange={(e) => up({ date_of_birth: e.target.value })} />
        </label>

        <label>Application date
          <input type="date" value={form.application_date}
            onChange={(e) => up({ application_date: e.target.value })} />
        </label>

        <label>Net monthly income (&#8377;)
          <input type="number" min={5000} step={5000} value={form.net_monthly_income}
            onChange={(e) => up({ net_monthly_income: Number(e.target.value) || 0 })} />
        </label>

        <label>Existing EMIs (&#8377;/mo)
          <input type="number" min={0} value={numVal(form.existing_monthly_emi)}
            placeholder="unknown" onChange={(e) => up({ existing_monthly_emi: onum(e.target.value) })} />
        </label>

        <label>Card outstanding (&#8377;)
          <input type="number" min={0} value={numVal(form.card_outstanding)}
            placeholder="unknown" onChange={(e) => up({ card_outstanding: onum(e.target.value) })} />
        </label>

        {!!form.card_outstanding && (
          <label>Card monthly payment (&#8377;/mo)
            <input type="number" min={0} value={numVal(form.card_monthly_payment)}
              placeholder="unknown" onChange={(e) => up({ card_monthly_payment: onum(e.target.value) })} />
          </label>
        )}

        <label className="checkbox">
          <input type="checkbox" checked={form.has_credit_score === true}
            onChange={(e) => up({ has_credit_score: e.target.checked })} />
          Has a credit score
        </label>

        {form.has_credit_score && (
          <label>Bureau score: <b>{form.bureau_score ?? "-"}</b>
            <input type="range" min={300} max={900} value={form.bureau_score ?? 750}
              onChange={(e) => up({ bureau_score: Number(e.target.value) })} />
          </label>
        )}

        <label>Max DPD, last 12m (days)
          <input type="number" min={0} value={numVal(form.max_dpd_days_last_12_months)}
            placeholder="unknown" onChange={(e) => up({ max_dpd_days_last_12_months: onum(e.target.value) })} />
        </label>

        <label>Enquiries, last 6m
          <input type="number" min={0} value={numVal(form.enquiries_last_6_months)}
            placeholder="unknown" onChange={(e) => up({ enquiries_last_6_months: onum(e.target.value) })} />
        </label>

        <label className="checkbox">
          <input type="checkbox" checked={form.has_settled_loan}
            onChange={(e) => up({ has_settled_loan: e.target.checked })} />
          Has a settled loan
        </label>

        {form.has_settled_loan && (
          <label>Settled (months ago)
            <input type="number" min={0} value={numVal(form.settled_loan_months_ago)}
              placeholder="unknown" onChange={(e) => up({ settled_loan_months_ago: onum(e.target.value) })} />
          </label>
        )}

        <label className="checkbox">
          <input type="checkbox" checked={form.write_off_flag}
            onChange={(e) => up({ write_off_flag: e.target.checked })} />
          Write-off on record
        </label>

        <label>Total experience (mo)
          <input type="number" min={0} value={numVal(form.total_experience_months)}
            placeholder="unknown" onChange={(e) => up({ total_experience_months: onum(e.target.value) })} />
        </label>

        <label>Current job (mo)
          <input type="number" min={0} value={numVal(form.current_job_tenure_months)}
            placeholder="unknown" onChange={(e) => up({ current_job_tenure_months: onum(e.target.value) })} />
        </label>

        <label>Employer category
          <select value={form.employer_category} onChange={(e) => up({ employer_category: e.target.value })}>
            <option value="">(not specified)</option>
            {meta.employer_categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        {isSE && (
          <>
            <label>Business vintage (mo)
              <input type="number" min={0} value={numVal(form.business_vintage_months)}
                placeholder="unknown" onChange={(e) => up({ business_vintage_months: onum(e.target.value) })} />
            </label>
            <label>ITR years available
              <input type="number" min={0} max={10} value={numVal(form.itr_years_available)}
                placeholder="unknown" onChange={(e) => up({ itr_years_available: onum(e.target.value) })} />
            </label>
            <label>Latest ITR income (&#8377;/yr)
              <input type="number" min={0} step={100000} value={numVal(form.itr_income_y1)}
                placeholder="unknown" onChange={(e) => up({ itr_income_y1: onum(e.target.value) })} />
            </label>
            {form.employment_type === "sep" && (
              <label>Profession
                <input type="text" placeholder="doctor / ca / cs" value={form.profession}
                  onChange={(e) => up({ profession: e.target.value })} />
              </label>
            )}
          </>
        )}

        <label>City
          <input type="text" value={form.city} onChange={(e) => up({ city: e.target.value })} />
        </label>

        <label>Salary account with
          <select value={form.salary_account_with}
            onChange={(e) => up({ salary_account_with: e.target.value })}>
            {meta.salary_account_options.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>

        <label>Gender (rate concessions)
          <select value={form.gender} onChange={(e) => up({ gender: e.target.value })}>
            <option>(not specified)</option>
            {meta.genders.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>

        <label>Requested amount (&#8377;)
          <input type="number" min={0} step={50000} value={numVal(form.requested_amount)}
            placeholder="none" onChange={(e) => up({ requested_amount: onum(e.target.value) })} />
        </label>

        <label>Tenure (months)
          <select value={form.requested_tenure_months ?? 0}
            onChange={(e) => up({ requested_tenure_months: Number(e.target.value) || null })}>
            <option value={0}>auto</option>
            {meta.tenures.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      </div>

      <div className="form-actions">
        <button type="submit" disabled={loading}>
          {loading ? "Checking\u2026" : "Check eligibility"}
        </button>
      </div>
    </form>
  );
}
