import { useState } from "react";
import { Decision, LenderOffer } from "../api";
import { pct, rupees } from "../format";

const STATUS_LABEL: Record<string, string> = {
  ELIGIBLE_TO_QUERY_LENDERS: "Eligible to query lender",
  PRELIMINARILY_ELIGIBLE: "Preliminarily eligible",
  NOT_ELIGIBLE: "Not eligible under rules",
  ADDITIONAL_INFORMATION_REQUIRED: "More information needed",
  MANUAL_REVIEW: "Manual review required",
  INVALID_INPUT: "Invalid input",
  RULES_UNAVAILABLE: "Eligibility could not be established",
};

function statusClass(s: string): string {
  if (s === "ELIGIBLE_TO_QUERY_LENDERS") return "st approve";
  if (s === "PRELIMINARILY_ELIGIBLE") return "st reduced";
  if (s === "ADDITIONAL_INFORMATION_REQUIRED" || s === "MANUAL_REVIEW") return "st review";
  return "st reject";
}

function isOffer(s: string): boolean {
  return s === "ELIGIBLE_TO_QUERY_LENDERS" || s === "PRELIMINARILY_ELIGIBLE";
}

function RuleTag({ status }: { status: string }) {
  const cls = status === "PUBLISHED" ? "tag pub" : status === "ESTIMATED" ? "tag est" : "tag oth";
  return <span className={cls}>{status.toLowerCase()}</span>;
}

function OfferRow({ offer }: { offer: LenderOffer }) {
  const [open, setOpen] = useState(false);
  const o = offer;
  const detail = o.reasons.length > 0 || o.fixes.length > 0 || isOffer(o.status);
  const p = o.pricing;
  return (
    <>
      <tr className={detail ? "clickable" : ""} onClick={() => detail && setOpen(!open)}>
        <td className="lender">
          {o.lender_id.toUpperCase()}
          <div className="prod">{o.product_label}</div>
        </td>
        <td><span className={statusClass(o.status)}>{STATUS_LABEL[o.status] ?? o.status}</span></td>
        <td className="num">{rupees(o.max_eligible.amount)}</td>
        <td className="num">{o.requested.amount ? rupees(o.requested.emi) : "-"}</td>
        <td className="num">{p.rate_is_range && p.rate_min_pa != null
          ? `${p.rate_min_pa}-${p.rate_max_pa}%` : pct(p.nominal_rate_pa)}</td>
        <td className="num">{pct(p.apr_pa)}</td>
        <td className="num">{o.strength_score ?? "-"}</td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={7}>
            {isOffer(o.status) && (
              <div className="detail-grid">
                <div>
                  <b>Requested loan</b>
                  <div>{o.requested.amount
                    ? `${rupees(o.requested.amount)} over ${o.requested.tenure_months} months`
                    : "no amount requested"}</div>
                  <div>{o.requested.amount ? `EMI ${rupees(o.requested.emi)}/mo` : ""}</div>
                  <div className={o.requested_supported ? "ok-txt" : "warn-txt"}>
                    {o.requested.amount
                      ? (o.requested_supported ? "requested amount is covered" : "requested amount exceeds the eligible maximum")
                      : ""}
                  </div>
                </div>
                <div>
                  <b>Maximum eligible</b>
                  <div>{rupees(o.max_eligible.amount)} over {o.max_eligible.tenure_months} months</div>
                  <div>EMI {rupees(o.max_eligible.emi)}/mo (at the max-eligibility tenure)</div>
                  <div className="muted">limited by: {o.caps.binding_cap}</div>
                </div>
                <div>
                  <b>Rate &amp; charges</b>
                  <div>Interest rate: {p.rate_is_range && p.rate_min_pa != null
                    ? `${p.rate_min_pa}-${p.rate_max_pa}% (range)` : pct(p.nominal_rate_pa)}</div>
                  <div>Processing fee: {rupees(p.processing_fee)} + GST {rupees(p.gst_on_fee)}</div>
                  <div>Net disbursement: {rupees(p.net_disbursement)}</div>
                  <div>Total repayment: {rupees(p.total_repayment)}</div>
                  <div>APR: {pct(p.apr_pa)} {p.apr_note && <span className="muted">({p.apr_note})</span>}</div>
                  {p.rate_source_url && (
                    <div className="muted">
                      rate source: <a href={p.rate_source_url} target="_blank" rel="noreferrer">link</a>
                      {p.rate_accessed_date ? ` (${p.rate_accessed_date})` : ""} <RuleTag status={(p.rate_confidence || "unknown").toUpperCase()} />
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
                      <code>{r.code}</code> {r.message} <RuleTag status={r.rule_status} />
                      {r.applicant_value && (
                        <span className="muted"> (you: {r.applicant_value}, needs: {r.required_value})</span>
                      )}
                      {r.source_url && (
                        <> {" "}<a href={r.source_url} target="_blank" rel="noreferrer">source</a></>
                      )}
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
          </td>
        </tr>
      )}
    </>
  );
}

export default function Results({ decision }: { decision: Decision }) {
  const offers = [...decision.offers].sort((a, b) => {
    const rank = (s: string) => (isOffer(s) ? 0 : 1);
    if (rank(a.status) !== rank(b.status)) return rank(a.status) - rank(b.status);
    return (a.pricing.apr_pa ?? 1e9) - (b.pricing.apr_pa ?? 1e9);
  });
  const nOffers = offers.filter((o) => isOffer(o.status)).length;
  const best = decision.best_offer;

  return (
    <div>
      <div className="summary">
        <div className={"badge " + (decision.eligible ? "ok" : "no")}>
          {decision.eligible ? "PRELIMINARY MATCHES FOUND" : "NO PRELIMINARY MATCH"}
        </div>
        <div className="metric"><span>{nOffers}/20</span> products matched</div>
        <div className="metric"><span>{decision.applicant_age}</span> years</div>
        {best && <div className="metric"><span>{pct(best.pricing.apr_pa)}</span> best APR</div>}
      </div>

      {best && (
        <div className="best">
          <b>Best: {best.lender_id.toUpperCase()}</b> &mdash; {best.product_label}.{" "}
          Max eligible {rupees(best.max_eligible.amount)} over {best.max_eligible.tenure_months} months
          (EMI {rupees(best.max_eligible.emi)}/mo).{" "}
          {best.requested.amount &&
            <>Requested {rupees(best.requested.amount)} over {best.requested.tenure_months} months
              = EMI {rupees(best.requested.emi)}/mo. </>}
          Rate {pct(best.pricing.nominal_rate_pa)}, APR {pct(best.pricing.apr_pa)}, strength {best.strength_score}/100.
          {best.rationale && <div className="muted" style={{ marginTop: 6 }}>{best.rationale}</div>}
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
            <th>Lender / product</th><th>Status</th><th>Max eligible</th>
            <th>EMI (requested)</th><th>Rate</th><th>APR</th><th>Strength</th>
          </tr>
        </thead>
        <tbody>{offers.map((o) => <OfferRow key={o.lender_id + o.product} offer={o} />)}</tbody>
      </table>
      <p className="rowhint">Click any row to see requested vs maximum amounts, the rate/fee/GST/APR breakdown, sources, and advice.</p>
      <p className="rowhint">{decision.disclaimer}</p>
    </div>
  );
}
