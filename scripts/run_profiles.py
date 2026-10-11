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
        appr = [o for o in d.offers if o.status != Status.REJECT]
        print(f"\n{pid} - {desc}  (age {d.applicant_age})")
        print(f"  eligible: {d.eligible}   offers: {len(appr)}/20")
        if d.best_offer:
            b = d.best_offer
            print(f"  best: {b.lender_id} {b.status.value} max Rs{b.max_loan:,.0f} "
                  f"rate {b.nominal_rate_pa}% APR {b.apr_pa}% EMI Rs{b.emi:,.0f} strength {b.strength_score}")
        top = sorted(appr, key=lambda o: o.apr_pa or 1e9)[:5]
        for o in top:
            print(f"    {o.lender_id:11} {o.status.value:15} max Rs{o.max_loan:>10,.0f} "
                  f"APR {o.apr_pa:>5}% [{o.binding_cap}]")
        if not d.eligible:
            print("  top blocking:", ", ".join(f"{r.code}" for r in d.top_blocking_reasons))


if __name__ == "__main__":
    main()
