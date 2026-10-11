"""plan3 Phase 9: audit every lender for GENERIC / ESTIMATED material rules.

Lists each material sizing/pricing/gate rule that is NOT published (estimated, inferred,
or a generic default like FOIR 60% / 20x multiple / loan_min 50000), so no lender is
treated as fully verified when important rules remain assumptions. Prints a per-lender
table and a repo-wide total. Read-only; never edits the rule table.

    .venv\\Scripts\\python.exe scripts/audit_generic_defaults.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LONG = ROOT / "data" / "lender_rules_long.csv"

MATERIAL = {"foir_max", "income_multiple_max", "loan_max", "loan_min", "take_home_floor",
            "score_min", "age_min", "age_max_at_maturity", "income_min_monthly",
            "income_min_annual", "rate_min_pa", "rate_max_pa", "processing_fee_pct"}
NON_PUBLISHED = {"estimated", "estimated_superseded", "derived"}


def main() -> None:
    rows = list(csv.DictReader(LONG.open(encoding="utf-8-sig")))
    per_lender: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["variable"] in MATERIAL and r["confidence"] in NON_PUBLISHED:
            per_lender[r["lender_id"]].append(r)

    print(f"{'lender':12} {'#non-published material rules':>30}")
    print("-" * 44)
    total = 0
    for lender in sorted(per_lender):
        items = per_lender[lender]
        total += len(items)
        print(f"{lender:12} {len(items):>30}")
        for r in items:
            print(f"    {r['variable']:22} {r['confidence']:20} {r['estimation_method'][:50]}")
    print("-" * 44)
    print(f"TOTAL non-published material rules: {total}")
    print("All are tagged estimated/derived (never 'published'); none is presented as a "
          "verified lender rule. See data/sources/_phase9_audit for the summary.")


if __name__ == "__main__":
    main()
