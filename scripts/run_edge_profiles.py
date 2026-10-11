"""Evaluate every EDGE profile and render a markdown results report."""
import datetime as dt
import json
from pathlib import Path

from eligibility.engine import Engine
from eligibility.schema import Applicant, Status

ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "tests" / "edge_profiles"
OUT = ROOT / "plan2_results.md"

STATUS_LABEL = {
    Status.ELIGIBLE_FOR_REQUESTED_TERMS: "Eligible (requested terms)",
    Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS: "Eligible (alternative terms)",
    Status.PRELIMINARILY_ELIGIBLE: "Preliminarily eligible",
    Status.NOT_ELIGIBLE: "Not eligible",
    Status.ADDITIONAL_INFORMATION_REQUIRED: "More info needed",
    Status.MANUAL_REVIEW: "Manual review",
    Status.INVALID_INPUT: "Invalid input",
    Status.RULES_UNAVAILABLE: "Rules unavailable",
}


def rup(n):
    return "-" if n is None else "Rs " + format(round(n), ",")


def pct(n):
    return "-" if n is None else f"{n}%"


def load(pid):
    return json.loads((EDGE / f"{pid}.json").read_text(encoding="utf-8"))


def applicant(raw):
    r = dict(raw)
    r.pop("profile_id", None)
    r.pop("description", None)
    return Applicant(**r)


STATUS_ORDER = [
    Status.ELIGIBLE_FOR_REQUESTED_TERMS, Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS,
    Status.PRELIMINARILY_ELIGIBLE, Status.ADDITIONAL_INFORMATION_REQUIRED,
    Status.MANUAL_REVIEW, Status.NOT_ELIGIBLE, Status.RULES_UNAVAILABLE,
]


def main():
    eng = Engine()
    lines = []
    w = lines.append
    today = dt.date.today().isoformat()
    w("# plan2 EDGE profiles — engine results\n")
    w(f"Generated {today} by `scripts/run_edge_profiles.py` over the real engine "
      f"(`eligibility.engine.Engine`). Inputs are the 10 EDGE profiles from "
      f"`prompts/plan2_inputs.md` (stored in `tests/edge_profiles/`).\n")
    w("All figures are screening estimates against published lender criteria — not loan offers. "
      "APR is an IRR on net-of-fee cash flows; `*` marks an indicative APR (rate estimated).\n")

    pids = sorted(p.stem for p in EDGE.glob("EDGE*.json"))
    # summary table
    w("## Summary\n")
    w("| Profile | Description | Age | Pass screening | Cover exact request | Best lender | Best APR |")
    w("|---|---|---|---|---|---|---|")
    cache = {}
    for pid in pids:
        raw = load(pid)
        app = applicant(raw)
        d = eng.run(app)
        cache[pid] = (raw, app, d)
        n_offer = sum(1 for o in d.offers if o.status.is_offer)
        n_cover = sum(1 for o in d.offers if o.status.covers_request)
        best = d.best_offer
        bl = best.lender_id.upper() if best else "-"
        ba = (pct(best.pricing.apr_pa) + ("" if (best and best.apr_reliable) else "*")) if best else "-"
        w(f"| {pid} | {raw.get('description','')} | {d.applicant_age} | {n_offer}/20 | "
          f"{n_cover}/20 | {bl} | {ba} |")
    w("")

    for pid in pids:
        raw, app, d = cache[pid]
        w(f"## {pid} — {raw.get('description','')}\n")
        # input echo
        w("**Input (canonical fields):**\n")
        w("```json")
        w(json.dumps(raw, indent=2))
        w("```\n")
        n_offer = sum(1 for o in d.offers if o.status.is_offer)
        n_cover = sum(1 for o in d.offers if o.status.covers_request)
        w(f"- Completed-years age: **{app.age_completed_years}** "
          f"(exact {d.applicant_age}); bureau state: **{app.bureau_state.value}**")
        w(f"- Products passing screening: **{n_offer}/20**; covering the exact "
          f"Rs {format(round(app.requested_amount),',') if app.requested_amount else '-'} "
          f"/ {app.requested_tenure_months}m request: **{n_cover}/20**")
        if d.best_offer:
            b = d.best_offer
            w(f"- Best option: **{b.lender_id.upper()} — {b.product_label}** "
              f"({STATUS_LABEL[b.status]}); APR {pct(b.pricing.apr_pa)}"
              f"{'' if b.apr_reliable else ' (indicative)'}")
            w(f"  - {b.rationale}")
        else:
            w("- Best option: **none** (no covering offer)")
        if not d.eligible and d.top_blocking_reasons:
            w(f"- Top blocking reasons: {', '.join(r.code for r in d.top_blocking_reasons)}")
        if d.indicative_lender_ids:
            w(f"- Indicative-only (estimated APR): {', '.join(l.upper() for l in d.indicative_lender_ids)}")
        w("")
        # per-lender table
        w("| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |")
        w("|---|---|---|---|---|---|---|---|---|")
        offers = sorted(d.offers, key=lambda o: (STATUS_ORDER.index(o.status),
                                                 o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9))
        for o in offers:
            p = o.pricing
            rate = (f"{p.rate_min_pa}-{p.rate_max_pa}%" if p.rate_is_range and p.rate_min_pa is not None
                    else pct(p.nominal_rate_pa))
            apr = pct(p.apr_pa) + ("" if o.apr_reliable else "*")
            remi = rup(o.requested.emi) if o.requested.amount else "-"
            w(f"| {o.lender_id.upper()} | {o.product_label} | {STATUS_LABEL[o.status]} | "
              f"{remi} | {rup(o.max_eligible.amount)} | {rate} | {apr} | "
              f"{o.strength_score if o.strength_score is not None else '-'} | "
              f"{o.caps.binding_cap or '-'} |")
        w("")
        # reasons for non-eligible / flagged
        flagged = [o for o in offers if o.reasons and not o.status.covers_request]
        if flagged:
            w("<details><summary>Reason codes for non-covering / flagged products</summary>\n")
            for o in flagged:
                codes = ", ".join(f"`{r.code}`" for r in o.reasons)
                w(f"- **{o.lender_id.upper()}** ({STATUS_LABEL[o.status]}): {codes}")
            w("\n</details>\n")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
