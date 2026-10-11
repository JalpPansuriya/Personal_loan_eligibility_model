import { useEffect, useState } from "react";
import { Decision, Meta, evaluate, getMeta } from "./api";
import { EMPTY_FORM, FormState, formFromJson, toInput, unknownKeys } from "./mapping";
import ApplicantForm from "./components/ApplicantForm";
import Results from "./components/Results";

export type { FormState } from "./mapping";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setError(String(e)));
  }, []);

  // Fill the form from a raw applicant JSON object (bundled profile or pasted payload).
  // Unknown keys are surfaced as a warning (never silently dropped); dates are preserved.
  function fillFromJson(obj: Record<string, unknown>): void {
    const unknown = unknownKeys(obj);
    setWarning(unknown.length ? `Ignored unsupported keys: ${unknown.join(", ")}` : null);
    setForm(formFromJson(obj));
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
          Rule-based screening against the published criteria of 20 selected Indian
          personal-loan lenders. APR is an estimate computed on net-of-fee cash flows; the
          interest rate, processing fee and 18% GST are shown separately. Not a loan offer.
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
        {warning && <div className="warn-box">{warning}</div>}
      </section>

      <section className="results-pane">
        {error && <div className="error">{error}</div>}
        {!decision && !error && <p className="hint">Fill the form and click <b>Check eligibility</b>.</p>}
        {decision && <Results decision={decision} />}
      </section>
    </div>
  );
}
