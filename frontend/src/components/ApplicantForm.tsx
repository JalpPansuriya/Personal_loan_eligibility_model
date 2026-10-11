import { useState } from "react";
import { Meta, getProfiles } from "../api";
import { FormState } from "../App";

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
  const num = (v: string) => (v === "" ? 0 : Number(v));
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

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="form-head">
        <h2>Applicant</h2>
      </div>

      <details className="json-box" onToggle={(e) => (e.target as HTMLDetailsElement).open && loadProfiles()}>
        <summary>Paste JSON / load a sample profile (auto-fills the form)</summary>
        <div className="json-actions">
          <select
            defaultValue=""
            onChange={(e) => {
              const p = profiles.find((x) => x.profile_id === e.target.value);
              if (p) {
                setJsonText(JSON.stringify(p, null, 2));
                onFillJson(p);
              }
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
          placeholder='{"employment_type":"salaried","net_monthly_income":90000,"bureau_score":770,"date_of_birth":"1994-01-01"}'
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
        />
        <div className="json-actions">
          <button type="button" className="secondary" onClick={applyJson}>
            Fill form from JSON
          </button>
          <span className="json-note">Unknown keys are ignored; date_of_birth becomes an age.</span>
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

        <label>
          Net monthly income (&#8377;)
          <input type="number" min={5000} step={5000} value={form.net_monthly_income}
            onChange={(e) => up({ net_monthly_income: num(e.target.value) })} />
        </label>

        <label>
          Existing EMIs (&#8377;/mo)
          <input type="number" min={0} step={1000} value={form.existing_emi_monthly}
            onChange={(e) => up({ existing_emi_monthly: num(e.target.value) })} />
        </label>

        <label>
          Card outstanding (&#8377;)
          <input type="number" min={0} step={5000} value={form.credit_card_outstanding}
            onChange={(e) => up({ credit_card_outstanding: num(e.target.value) })} />
        </label>

        <label>
          Age: <b>{form.age}</b>
          <input type="range" min={18} max={75} value={form.age}
            onChange={(e) => up({ age: num(e.target.value) })} />
        </label>

        <label className="checkbox">
          <input type="checkbox" checked={form.has_score}
            onChange={(e) => up({ has_score: e.target.checked })} />
          Has a credit score
        </label>

        {form.has_score && (
          <label>
            Bureau score: <b>{form.bureau_score}</b>
            <input type="range" min={300} max={900} value={form.bureau_score}
              onChange={(e) => up({ bureau_score: num(e.target.value) })} />
          </label>
        )}

        <label>
          Total experience (mo)
          <input type="number" min={0} step={6} value={form.total_experience_months}
            onChange={(e) => up({ total_experience_months: num(e.target.value) })} />
        </label>

        <label>
          Current job (mo)
          <input type="number" min={0} step={6} value={form.current_job_tenure_months}
            onChange={(e) => up({ current_job_tenure_months: num(e.target.value) })} />
        </label>

        <label>
          Employer category
          <select value={form.employer_category} onChange={(e) => up({ employer_category: e.target.value })}>
            {meta.employer_categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>

        {isSE && (
          <>
            <label>
              Business vintage (mo)
              <input type="number" min={0} step={6} value={form.business_vintage_months}
                onChange={(e) => up({ business_vintage_months: num(e.target.value) })} />
            </label>
            <label>
              ITR years filed
              <input type="number" min={0} max={10} value={form.itr_years_filed}
                onChange={(e) => up({ itr_years_filed: num(e.target.value) })} />
            </label>
            <label>
              Latest ITR income (&#8377;/yr)
              <input type="number" min={0} step={100000} value={form.itr_income_y1}
                onChange={(e) => up({ itr_income_y1: num(e.target.value) })} />
            </label>
            {form.employment_type === "sep" && (
              <label>
                Profession
                <input type="text" placeholder="doctor / ca / cs" value={form.profession}
                  onChange={(e) => up({ profession: e.target.value })} />
              </label>
            )}
          </>
        )}

        <label>
          City
          <input type="text" value={form.city} onChange={(e) => up({ city: e.target.value })} />
        </label>

        <label>
          Salary account with
          <select value={form.salary_account_with_lender}
            onChange={(e) => up({ salary_account_with_lender: e.target.value })}>
            {meta.salary_account_options.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </label>

        <label>
          Gender (rate concessions)
          <select value={form.gender} onChange={(e) => up({ gender: e.target.value })}>
            <option>(not specified)</option>
            {meta.genders.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </label>

        <label>
          Requested amount (&#8377;)
          <input type="number" min={0} step={50000} value={form.requested_amount}
            onChange={(e) => up({ requested_amount: num(e.target.value) })} />
        </label>

        <label>
          Tenure (months)
          <select value={form.requested_tenure_months}
            onChange={(e) => up({ requested_tenure_months: num(e.target.value) })}>
            <option value={0}>auto</option>
            {meta.tenures.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
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
