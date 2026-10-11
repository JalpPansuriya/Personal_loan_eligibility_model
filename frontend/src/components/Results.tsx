import { useState } from "react";
import { Decision, LenderOffer } from "../api";
import { pct, rupees } from "../format";

const STATUS_LABEL: Record<string, string> = {
  ELIGIBLE_FOR_REQUESTED_TERMS: "Eligible for requested terms",
  ELIGIBLE_FOR_ALTERNATIVE_TERMS: "Eligible for alternative terms",
  PRELIMINARILY_ELIGIBLE: "Preliminarily eligible",
  NOT_ELIGIBLE: "Not eligible under rules",
  ADDITIONAL_INFORMATION_REQUIRED: "More information needed",
  MANUAL_REVIEW: "Manual review required",
  INVALID_INPUT: "Invalid input",
  RULES_UNAVAILABLE: "Eligibility could not be established",
};

const OFFER_STATUSES = new Set([
  "ELIGIBLE_FOR_REQUESTED_TERMS", "ELIGIBLE_FOR_ALTERNATIVE_TERMS", "PRELIMINARILY_ELIGIBLE",
]);

function statusClass(s: string): string {
  if (s === "ELIGIBLE_FOR_REQUESTED_TERMS") return "st eligible";
  if (s === "ELIGIBLE_FOR_ALTERNATIVE_TERMS") return "st alt";
  if (s === "PRELIMINARILY_ELIGIBLE") return "st reduced";
  if (s === "ADDITIONAL_INFORMATION_REQUIRED" || s === "MANUAL_REVIEW") return "st review";
  return "st reject";
}

const isOffer = (s: string) => OFFER_STATUSES.has(s);

function RuleTag({ label }: { label: string }) {
  const l = label.toUpperCase();
  const cls = l === "VERIFIED_PUBLISHED" || l === "PUBLISHED" ? "tag pub"
    : l === "ESTIMATED" || l === "INFERRED" ? "tag est"
    : l === "CONFLICT_REQUIRES_REVIEW" ? "tag conflict" : "tag oth";
  return <span className={cls}>{label.toLowerCase()}</span>;
}

// an EMI is only ever shown next to the principal + tenure + rate it was computed on
function EmiLine({ label, amount, tenure, emi, rate }:
  { label: string; amount: number | null; tenure: number | null; emi: number | null; rate: number | null }) {
  if (amount == null) return <div className="muted">{label}: not applicable</div>;
  return (
    <div>
      <b>{label}</b>: {rupees(amount)} over {tenure} months @ {pct(rate)} &rarr; EMI {rupees(emi)}/mo
    </div>
  );
}

function OfferRow({ offer }: { offer: LenderOffer }) {
  const [open, setOpen] = useState(false);
  const o = offer;
  const p = o.pricing;
  const detail = o.reasons.length > 0 || o.fixes.length > 0 || isOffer(o.status);
  const rateCell = p.rate_is_range && p.rate_min_pa != null
    ? `${p.rate_min_pa}-${p.rate_max_pa}%` : pct(p.nominal_rate_pa);
  const reqEmi = o.requested.amount ? rupees(o.requested.emi) : "-";
  return (
    <>
      <tr className={detail ? "clickable" : ""} onClick={() => detail && setOpen(!open)}>
        <td className="lender">{o.lender_id.toUpperCase()}<div className="prod">{o.product_label}</div></td>
        <td><span className={statusClass(o.status)}>{STATUS_LABEL[o.status] ?? o.status}</span></td>
        <td className="num">{o.requested.amount ? rupees(o.requested.amount) : "-"}</td>
        <td className="num">{reqEmi}</td>
        <td className="num">{rupees(o.max_eligible.amount)}</td>
        <td className="num">{rateCell}</td>
        <td className="num">{pct(p.apr_pa)}{!o.apr_reliable && <span className="muted">*</span>}</td>
        <td className="num">{o.strength_score ?? "-"}</td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={8}>
            {isOffer(o.status) && (
              <div className="detail-grid">
                <div>
                  <b>Requested loan</b>
                  <EmiLine label="Requested" amount={o.requested.amount}
                    tenure={o.requested.tenure_months} emi={o.requested.emi} rate={p.nominal_rate_pa} />
                  <div className={o.requested_supported ? "ok-txt" : "warn-txt"}>
                    {o.requested.amount
                      ? (o.requested_supported ? "requested amount is covered"
                         : "requested amount exceeds the eligible maximum")
                      : "no amount requested"}
                  </div>
                  {!o.requested_tenure_supported && (
                    <div className="warn-txt">requested tenure outside the permitted range</div>
                  )}
                </div>
                {o.alternative.amount != null && (
                  <div>
                    <b>Alternative (not a sanction)</b>
                    <EmiLine label="Alternative" amount={o.alternative.amount}
                      tenure={o.alternative.tenure_months} emi={o.alternative.emi} rate={p.nominal_rate_pa} />
                  </div>
                )}
                <div>
                  <b>Maximum eligible</b>
                  <EmiLine label="Max" amount={o.max_eligible.amount}
                    tenure={o.max_eligible.tenure_months} emi={o.max_eligible.emi} rate={p.nominal_rate_pa} />
                  <div className="muted">limited by: {o.caps.binding_cap}</div>
                  {o.caps.selective_exception_possible && (
                    <div className="muted">{o.caps.selective_exception_note}</div>
                  )}
                </div>
                <div>
                  <b>Rate &amp; charges</b>
                  <div>Interest rate: {rateCell}{p.rate_is_range ? " (band)" : ""}</div>
                  {p.rate_capped_at_ceiling && (
                    <div className="warn-txt">rate capped at the published maximum ({pct(p.rate_max_pa)}); true applicant rate unknown</div>
                  )}
                  <div>Processing fee: {rupees(p.processing_fee)} + GST {rupees(p.gst_on_fee)}</div>
                  <div>Net disbursement: {rupees(p.net_disbursement)}</div>
                  <div>Total repayment: {rupees(p.total_repayment)}</div>
                  <div>Total cost of credit: {rupees(p.total_cost_of_credit)}</div>
                  <div>APR (est.): {pct(p.apr_pa)}{!o.apr_reliable && " — indicative"}</div>
                  {p.apr_note && <div className="muted">{p.apr_note}</div>}
                  {p.rate_source_url && (
                    <div className="muted">
                      rate source: <a href={p.rate_source_url} target="_blank" rel="noreferrer">link</a>
                      {p.rate_accessed_date ? ` (${p.rate_accessed_date})` : ""}{" "}
                      <RuleTag label={(p.rate_confidence || "unknown")} />
                    </div>
                  )}
                </div>
              </div>
            )}
            {o.reasons.length > 0 && (
              <div>
                <b>Why</b>
                <ul>
                  {o.reasons.map((r, i) => (
                    <li key={i}>
                      <code>{r.code}</code> {r.message} <RuleTag label={r.confidence_label || r.rule_status} />
                      {r.applicant_value && (
                        <span className="muted"> (you: {r.applicant_value}, needs: {r.required_value})</span>
                      )}
                      {r.source_url && (<> {" "}<a href={r.source_url} target="_blank" rel="noreferrer">source</a></>)}
                      {r.next_action && <div className="next">&rarr; {r.next_action}</div>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {o.fixes.length > 0 && (
              <div>
                <b>How to qualify</b>
                <ul>{o.fixes.map((f, i) => <li key={i} className="fix">{f.description}</li>)}</ul>
              </div>
            )}
            {o.checks.length > 0 && (
              <details className="checks">
                <summary>Decision trace ({o.checks.length} rules checked)</summary>
                <table className="checks-tbl">
                  <thead><tr><th>Rule</th><th>Status</th><th>You</th><th>Required</th><th>Source</th></tr></thead>
                  <tbody>
                    {o.checks.map((c, i) => (
                      <tr key={i} className={"chk-" + c.status.toLowerCase()}>
                        <td>{c.rule}</td>
                        <td>{c.status}</td>
                        <td>{c.actual_value ?? "-"}</td>
                        <td>{c.required_value ?? "-"}</td>
                        <td>
                          <RuleTag label={c.source_status} />
                          {c.source_url && <> <a href={c.source_url} target="_blank" rel="noreferrer">link</a></>}
                          {c.retrieved_at ? ` ${c.retrieved_at}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function Results({ decision }: { decision: Decision }) {
  const order = ["ELIGIBLE_FOR_REQUESTED_TERMS", "ELIGIBLE_FOR_ALTERNATIVE_TERMS",
    "PRELIMINARILY_ELIGIBLE", "ADDITIONAL_INFORMATION_REQUIRED", "MANUAL_REVIEW",
    "NOT_ELIGIBLE", "RULES_UNAVAILABLE"];
  const offers = [...decision.offers].sort((a, b) => {
    const ra = order.indexOf(a.status), rb = order.indexOf(b.status);
    if (ra !== rb) return ra - rb;
    return (a.pricing.apr_pa ?? 1e9) - (b.pricing.apr_pa ?? 1e9);
  });
  const count = (s: string) => offers.filter((o) => o.status === s).length;
  const nOffers = offers.filter((o) => isOffer(o.status)).length;
  const nCovering = count("ELIGIBLE_FOR_REQUESTED_TERMS");
  const nAlt = count("ELIGIBLE_FOR_ALTERNATIVE_TERMS");
  const nReview = count("MANUAL_REVIEW");
  const nInfo = count("ADDITIONAL_INFORMATION_REQUIRED");
  const best = decision.best_offer;
  const rk = decision.rankings;
  const lenderOf = (id: string | null) => (id ? id.toUpperCase() : "\u2014");

  return (
    <div>
      <div className="summary">
        <div className={"badge " + (decision.eligible ? "ok" : "no")}>
          {decision.eligible ? "PRELIMINARY MATCHES FOUND" : "NO PRELIMINARY MATCH"}
        </div>
        <div className="metric"><span>{nOffers}/20</span> pass screening</div>
        <div className="metric"><span>{nCovering}</span> cover exact request</div>
        <div className="metric"><span>{nAlt}</span> alternative only</div>
        <div className="metric"><span>{nReview}</span> manual review</div>
        <div className="metric"><span>{nInfo}</span> need more info</div>
        <div className="metric"><span>{decision.applicant_age}</span> years</div>
      </div>

      {rk && (
        <div className="rankings">
          <b>Rankings</b> <span className="muted">({rk.basis})</span>
          <ul>
            <li>Best for the exact requested terms: <b>{lenderOf(rk.best_for_requested_terms)}</b></li>
            <li>Best supported alternative: <b>{lenderOf(rk.best_supported_alternative)}</b></li>
            <li>Lowest estimated nominal rate: <b>{lenderOf(rk.lowest_estimated_rate)}</b> <span className="muted">(advertised, not APR)</span></li>
            <li>Lowest reliably-calculated APR: <b>{lenderOf(rk.lowest_reliable_apr)}</b></li>
          </ul>
          {rk.insufficient_evidence && <div className="warn-txt">Insufficient evidence for a reliable best option.</div>}
        </div>
      )}

      {best && (
        <div className="best">
          <b>Best: {best.lender_id.toUpperCase()}</b> &mdash; {best.product_label}{" "}
          (<span className={statusClass(best.status)}>{STATUS_LABEL[best.status]}</span>).{" "}
          {best.requested.amount
            ? <>Requested {rupees(best.requested.amount)} over {best.requested.tenure_months} months
                = EMI {rupees(best.requested.emi)}/mo @ {pct(best.pricing.nominal_rate_pa)}. </>
            : <>Max eligible {rupees(best.max_eligible.amount)} over {best.max_eligible.tenure_months} months
                (EMI {rupees(best.max_eligible.emi)}/mo). </>}
          APR {pct(best.pricing.apr_pa)}{!best.apr_reliable && " (indicative)"}.
          {best.rationale && <div className="muted" style={{ marginTop: 6 }}>{best.rationale}</div>}
        </div>
      )}

      {decision.indicative_lender_ids.length > 0 && (
        <div className="blocking">
          Indicative only (APR rests on an estimated rate): {decision.indicative_lender_ids.map((l) => l.toUpperCase()).join(", ")}
        </div>
      )}

      {!decision.eligible && decision.top_blocking_reasons.length > 0 && (
        <div className="blocking">
          Top blocking reasons: {decision.top_blocking_reasons.map((r) => r.code).join(", ")}
        </div>
      )}

      <table className="offers">
        <thead>
          <tr>
            <th>Lender / product</th><th>Status</th><th>Requested</th><th>EMI (requested)</th>
            <th>Max eligible</th><th>Rate</th><th>APR</th><th>Fit</th>
          </tr>
        </thead>
        <tbody>{offers.map((o) => <OfferRow key={o.lender_id + o.product} offer={o} />)}</tbody>
      </table>
      <p className="rowhint">Click any row for requested / alternative / maximum amounts, each EMI with its principal, rate and tenure, the fee/GST/APR breakdown, sources, and advice. * = APR is indicative (rate estimated).</p>
      <p className="rowhint">{decision.score_method}</p>
      <p className="rowhint">{decision.disclaimer}</p>
      <p className="rowhint muted">rule-set version: {decision.rule_set_version}</p>
    </div>
  );
}
