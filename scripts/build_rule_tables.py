"""Merge data/rules/{lender}.csv into the repo's rule tables.

Outputs (all regenerated; never hand-edit):
  data/lender_rules_long.csv   every atomic rule, one row each (source of truth for the engine)
  data/conflicts.csv           every variable where a lender's own pages disagree, with the
                               value the engine uses (agreed policy: stricter value) and the alternatives
  data/lender_rules_wide.csv   one row per lender x segment: the value the engine uses per key variable,
                               plus its confidence and source (the brief's "one row for each lender")

Usage: .venv\\Scripts\\python.exe scripts/build_rule_tables.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from verify_rules import HEADER

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "data" / "rules"
DATA = ROOT / "data"

# For each numeric variable, which direction is "stricter" for the applicant.
STRICTER_HIGHER = {  # a higher value is harder to meet
    "age_min", "income_min_monthly", "income_min_annual", "household_income_min_annual",
    "household_income_min_monthly", "exp_total_min_months", "exp_current_min_months",
    "business_vintage_min_months", "post_qualification_exp_min_months", "itr_years_min", "score_min",
    "relationship_min_months", "residence_stability_min_months", "loan_min", "tenure_min_months",
    "rate_min_pa", "rate_max_pa", "processing_fee_pct", "processing_fee_min_inr", "processing_fee_max_inr",
    "processing_fee_flat_inr", "take_home_floor",
}
STRICTER_LOWER = {  # a lower value is harder to meet / gives less credit
    "age_max_at_application", "age_max_at_maturity", "foir_max", "income_multiple_max", "loan_max",
    "tenure_max_months", "max_active_loans",
}
STRICTER_BOOL_FALSE = {"segment_offered", "ntc_allowed"}          # stricter = no
STRICTER_BOOL_TRUE = {"salary_account_required", "guarantor_required", "co_applicant_required"}  # stricter = yes
KEY_VARS = [  # columns of the wide table
    "segment_offered", "age_min", "age_max_at_application", "age_max_at_maturity", "income_min_monthly",
    "exp_total_min_months", "exp_current_min_months", "business_vintage_min_months", "itr_years_min",
    "score_min", "ntc_allowed", "salary_account_required", "foir_max", "income_multiple_max",
    "loan_min", "loan_max", "tenure_min_months", "tenure_max_months", "rate_min_pa", "rate_max_pa",
    "processing_fee_pct", "processing_fee_flat_inr",
]
CONF_RANK = {"published": 0, "published_conflict": 1, "derived": 2, "estimated": 3, "estimated_superseded": 9}


def num(v: str) -> float | None:
    try:
        return float(v.replace(",", "").strip())
    except ValueError:
        return None


def load() -> list[dict]:
    rows = []
    for f in sorted(RULES.glob("*.csv")):
        with f.open(encoding="utf-8-sig", newline="") as fh:
            rows.extend(csv.DictReader(fh))
    # calibrated rules from lender calculators (scripts/fit_calibration.py)
    cal = DATA / "calibration" / "derived_rules.csv"
    if cal.exists():
        with cal.open(encoding="utf-8") as fh:
            derived = [r for r in csv.DictReader(fh) if r["operator"] != "info"]
        keys = {(r["lender_id"], r["product"], r["segment"], r["variable"]) for r in derived}
        # a calibrated value supersedes the estimated default for the same variable
        for r in rows:
            if (r["lender_id"], r["product"], r["segment"], r["variable"]) in keys and r["confidence"] == "estimated":
                r["notes"] = (r["notes"] + " | " if r["notes"] else "") + "superseded by calculator calibration"
                r["confidence"] = "estimated_superseded"
        with cal.open(encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def is_false(c: dict) -> bool:
    return c["operator"] == "not_offered" or c["value"].strip().lower() in {"false", "no", "0", "not_offered"}


def pick(cands: list[dict], var: str) -> tuple[dict, list[dict]]:
    """Choose the row the engine uses. Prefer non-estimated rows; then apply the
    stricter-value policy (numeric direction, or the restrictive side of a yes/no).
    Returns (chosen, alternatives)."""
    best_rank = min(CONF_RANK[c["confidence"]] for c in cands)
    pool = [c for c in cands if CONF_RANK[c["confidence"]] <= max(best_rank, 1)] or cands
    chosen = pool[0]
    if var in STRICTER_BOOL_FALSE:  # restrictive answer = not offered / not allowed
        chosen = next((c for c in pool if is_false(c)), pool[0])
    elif var in STRICTER_BOOL_TRUE:  # restrictive answer = required
        chosen = next((c for c in pool if not is_false(c)), pool[0])
    else:
        nums = [(num(c["value"]), c) for c in pool if num(c["value"]) is not None]
        if not nums and var in STRICTER_HIGHER | STRICTER_LOWER:
            # text-only rows (e.g. "remaining period of service") can't drive the engine;
            # fall back to the best-confidence numeric row, even if estimated
            nums = [(num(c["value"]), c) for c in cands if num(c["value"]) is not None]
        if nums:
            if var in STRICTER_HIGHER:
                chosen = max(nums, key=lambda t: t[0])[1]
            elif var in STRICTER_LOWER:
                chosen = min(nums, key=lambda t: t[0])[1]
            else:
                chosen = nums[0][1]
    return chosen, [c for c in cands if c is not chosen]


def main() -> None:
    rows = load()
    with (DATA / "lender_rules_long.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)

    # group unconditional rules by lender/product/segment/variable
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["variable"] == "rate_grid" or r["effect"] == "info" and r["variable"] not in KEY_VARS:
            continue
        if r["confidence"] == "estimated_superseded" or r["operator"] == "info":
            continue
        groups[(r["lender_id"], r["product"], r["segment"], r["variable"], r["condition"].strip())].append(r)

    conflicts = []
    chosen_by: dict[tuple, dict] = {}
    for key, cands in groups.items():
        chosen, alts = pick(cands, key[3])
        chosen_by[key] = chosen
        distinct = {c["value"].strip() for c in cands}
        if len(cands) > 1 and (len(distinct) > 1 or any(c["confidence"] == "published_conflict" for c in cands)):
            conflicts.append({
                "lender_id": key[0], "product": key[1], "segment": key[2], "variable": key[3],
                "condition": key[4], "engine_value": chosen["value"], "engine_rule_id": chosen["rule_id"],
                "engine_confidence": chosen["confidence"],
                "policy": ("stricter value" if key[3] in STRICTER_HIGHER | STRICTER_LOWER | STRICTER_BOOL_FALSE
                           | STRICTER_BOOL_TRUE else "first published"),
                "alternatives": " ; ".join(f"{a['value']} [{a['rule_id']}, {a['confidence']}]" for a in alts),
                "sources": " ; ".join(sorted({c["source_url"] for c in cands if c["source_url"]})),
            })
    cf_fields = ["lender_id", "product", "segment", "variable", "condition", "engine_value", "engine_rule_id",
                 "engine_confidence", "policy", "alternatives", "sources"]
    with (DATA / "conflicts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cf_fields)
        w.writeheader()
        w.writerows(sorted(conflicts, key=lambda c: (c["lender_id"], c["product"], c["variable"])))

    # wide table: lender x product x segment, unconditional (base) value per key variable
    wide: dict[tuple, dict] = {}
    for (lender, product, segment, var, cond), r in chosen_by.items():
        if cond or var not in KEY_VARS:
            continue
        row = wide.setdefault((lender, product, segment), {"lender_id": lender, "product": product, "segment": segment})
        row[var] = r["value"]
        row[f"{var}__conf"] = r["confidence"]
        row[f"{var}__src"] = r["source_url"]
    fields = ["lender_id", "product", "segment"]
    for v in KEY_VARS:
        fields += [v, f"{v}__conf", f"{v}__src"]
    with (DATA / "lender_rules_wide.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(sorted(wide.values(), key=lambda r: (r["lender_id"], r["product"], r["segment"])))

    print(f"lender_rules_long.csv: {len(rows)} rules")
    print(f"conflicts.csv: {len(conflicts)} variables with disagreeing values")
    print(f"lender_rules_wide.csv: {len(wide)} lender/product/segment rows")


if __name__ == "__main__":
    main()
