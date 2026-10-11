"""Run all P01-P16 profiles through the engine and print a compact review summary."""
from __future__ import annotations

import json
from pathlib import Path

from eligibility.engine import Engine
from eligibility.schema import Applicant, Status

PROF = Path(__file__).resolve().parents[1] / "tests" / "profiles"


def main() -> None:
    engine = Engine()
    for pf in sorted(PROF.glob("P*.json")):
        rec = json.loads(pf.read_text(encoding="utf-8"))
        pid = rec.pop("profile_id")
        desc = rec.pop("description")
        app = Applicant(**rec)
        d = engine.run(app)
        appr = [o for o in d.offers if o.status not in (Status.NOT_ELIGIBLE, Status.INVALID_INPUT, Status.RULES_UNAVAILABLE)]
        print(f"\n{pid} - {desc}  (age {d.applicant_age:.1f})")
        print(f"  eligible: {d.eligible}   offers: {len(appr)}/20")
        if d.best_offer:
            b = d.best_offer
            b_amt = b.requested.amount or b.max_eligible.amount or 0
            b_rate = f"{b.pricing.nominal_rate_pa}%" if b.pricing.nominal_rate_pa is not None else "N/A"
            b_apr = f"{b.pricing.apr_pa}%" if b.pricing.apr_pa is not None else "N/A"
            b_emi = b.requested.emi or b.max_eligible.emi or 0
            print(f"  best: {b.lender_id} {b.status.value} max Rs{b_amt:,.0f} "
                  f"rate {b_rate} APR {b_apr} EMI Rs{b_emi:,.0f} strength {b.strength_score}")
        top = sorted(appr, key=lambda o: o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9)[:5]
        for o in top:
            o_amt = o.requested.amount or o.max_eligible.amount or 0
            o_apr_str = f"{o.pricing.apr_pa:>5.2f}%" if o.pricing.apr_pa is not None else "  N/A"
            print(f"    {o.lender_id:11} {o.status.value:15} max Rs{o_amt:>10,.0f} "
                  f"APR {o_apr_str} [{o.caps.binding_cap}]")
        if not d.eligible:
            print("  top blocking:", ", ".join(f"{r.code}" for r in d.top_blocking_reasons))


if __name__ == "__main__":
    main()
