"""Freeze the current engine output for P01-P16 as golden JSON (reviewed baseline).

Run after a reviewed change:
  .venv\\Scripts\\python.exe scripts/freeze_golden.py
Each golden file stores the per-lender status/max_loan/apr and the best offer, so the
Phase 7 gate can detect any unintended change.
"""
from __future__ import annotations

import json
from pathlib import Path

from eligibility.engine import Engine
from eligibility.schema import Applicant

ROOT = Path(__file__).resolve().parents[1]
PROF = ROOT / "tests" / "profiles"
GOLD = ROOT / "tests" / "golden"
GOLD.mkdir(parents=True, exist_ok=True)


def summarize(app: Applicant, engine: Engine) -> dict:
    d = engine.run(app)
    return {
        "eligible": d.eligible,
        "offer_count": sum(1 for o in d.offers if o.status.is_offer),
        "best": None if not d.best_offer else {
            "lender_id": d.best_offer.lender_id,
            "status": d.best_offer.status.value,
            "max_eligible": d.best_offer.max_eligible.amount,
            "apr_pa": d.best_offer.pricing.apr_pa,
        },
        "offers": {
            o.lender_id: {"status": o.status.value,
                          "max_eligible": o.max_eligible.amount,
                          "apr_pa": o.pricing.apr_pa}
            for o in d.offers
        },
    }


def main() -> None:
    engine = Engine()
    for pf in sorted(PROF.glob("P*.json")):
        rec = json.loads(pf.read_text(encoding="utf-8"))
        rec.pop("profile_id", None)
        rec.pop("description", None)
        app = Applicant(**rec)
        out = summarize(app, engine)
        (GOLD / f"{pf.stem}.json").write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"froze {len(list(PROF.glob('P*.json')))} golden outputs to {GOLD}")


if __name__ == "__main__":
    main()
