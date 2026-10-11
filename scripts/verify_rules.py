"""Verify data/rules/*.csv against the spec and the saved snapshots.

Checks per row: header/columns, controlled vocabulary, confidence-specific requirements,
source_file exists, and that every published/published_conflict quote is an exact
substring of its snapshot after whitespace collapse.

Usage: .venv\\Scripts\\python.exe scripts/verify_rules.py [lender ...]
Exit code 1 if any row fails.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "data" / "rules"
SRC = ROOT / "data" / "sources"

HEADER = ["rule_id", "lender_id", "product", "segment", "variable", "operator", "value", "unit", "effect",
          "condition", "source_url", "source_file", "accessed_date", "confidence", "estimation_method", "quote", "notes"]
LENDERS = {"sbi", "hdfc", "icici", "axis", "kotak", "bob", "pnb", "canara", "union", "indusind", "idfc", "yes",
           "bajaj", "tata", "abcl", "lnt", "poonawalla", "navi", "kreditbee", "moneyview"}
SEGMENTS = {"salaried", "sep", "seb", "all"}
OPERATORS = {">=", "<=", ">", "<", "==", "in", "not_offered", "range", "formula", "grid", "info"}
EFFECTS = {"gate", "amount_cap", "foir", "multiple", "rate", "tenure", "fee", "pricing_modifier", "info"}
CONFIDENCE = {"published", "published_conflict", "derived", "estimated"}
VARIABLES = {
    "segment_offered", "age_min", "age_max_at_application", "age_max_at_maturity", "income_min_monthly",
    "income_min_annual", "household_income_min_annual", "household_income_min_monthly", "exp_total_min_months",
    "exp_current_min_months", "business_vintage_min_months", "post_qualification_exp_min_months", "itr_years_min",
    "score_min", "score_preferred", "ntc_allowed", "employer_category_allowed", "profession_allowed",
    "salary_account_required", "relationship_min_months", "residence_stability_min_months", "city_serviced",
    "nationality", "education_min", "co_applicant_required", "guarantor_required", "max_active_loans",
    "foir_max", "take_home_floor", "income_multiple_max", "loan_min", "loan_max", "tenure_min_months",
    "tenure_max_months", "rate_min_pa", "rate_max_pa", "rate_mean_pa", "rate_grid", "rate_benchmark", "apr_min",
    "apr_max", "processing_fee_pct", "processing_fee_min_inr", "processing_fee_max_inr", "processing_fee_flat_inr",
    "processing_fee_waiver", "gst_on_fee", "documentation_fee_inr", "foreclosure", "penal_charge",
    "bounce_charge", "lending_entity",
    # approved additions
    "bureau_reject_signal", "income_mode",
}

_ws = re.compile(r"\s+")
_cache: dict[str, str] = {}


def norm(s: str) -> str:
    # collapse whitespace and unify common unicode punctuation/rupee glyph variants
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    # table-cell separators written by the DOM capture (" | ") are layout, not content
    s = s.replace(" | ", " ").replace("| ", " ").replace(" |", " ")
    return _ws.sub(" ", s).strip()


def snapshot_text(name: str) -> str | None:
    if name not in _cache:
        p = SRC / name
        if not p.exists() and p.suffix == ".pdf":
            p = p.with_suffix(".txt")
        if not p.exists():
            return None
        _cache[name] = norm(p.read_text(encoding="utf-8", errors="replace"))
    return _cache[name]


def check_file(path: Path) -> tuple[int, list[str], Counter]:
    errors: list[str] = []
    conf = Counter()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if header != HEADER:
            return 0, [f"{path.name}: bad header {header}"], conf
        rows = list(reader)
    ids = set()
    for n, row in enumerate(rows, start=2):
        where = f"{path.name}:{n}"
        if len(row) != len(HEADER):
            errors.append(f"{where}: {len(row)} columns, expected {len(HEADER)}")
            continue
        r = dict(zip(HEADER, row))
        rid = r["rule_id"]
        if rid in ids:
            errors.append(f"{where}: duplicate rule_id {rid}")
        ids.add(rid)
        for col, allowed in (("lender_id", LENDERS), ("segment", SEGMENTS), ("operator", OPERATORS),
                             ("effect", EFFECTS), ("confidence", CONFIDENCE), ("variable", VARIABLES)):
            if r[col] not in allowed:
                errors.append(f"{where} [{rid}]: {col}={r[col]!r} not allowed")
        if r["lender_id"] != path.stem:
            errors.append(f"{where} [{rid}]: lender_id {r['lender_id']} != file {path.stem}")
        c = r["confidence"]
        conf[c] += 1
        if c in ("derived", "estimated") and not r["estimation_method"].strip():
            errors.append(f"{where} [{rid}]: {c} row needs estimation_method")
        if c in ("published", "published_conflict"):
            q = norm(r["quote"])
            if not q:
                errors.append(f"{where} [{rid}]: {c} row has empty quote")
                continue
            if len(q) > 300:
                errors.append(f"{where} [{rid}]: quote longer than 300 chars")
            if not r["source_file"]:
                errors.append(f"{where} [{rid}]: missing source_file")
                continue
            text = snapshot_text(r["source_file"])
            if text is None:
                errors.append(f"{where} [{rid}]: source_file not found: {r['source_file']}")
            elif q not in text:
                errors.append(f"{where} [{rid}]: quote not found in {r['source_file']}: {q[:90]!r}")
        if c == "estimated" and r["quote"].strip():
            errors.append(f"{where} [{rid}]: estimated row must have empty quote")
    return len(rows), errors, conf


def main(only: list[str]) -> int:
    files = sorted(RULES.glob("*.csv"))
    if only:
        files = [f for f in files if f.stem in only]
    total_rows, total_err, grand = 0, 0, Counter()
    for f in files:
        n, errs, conf = check_file(f)
        total_rows += n
        total_err += len(errs)
        grand += conf
        status = "PASS" if not errs else f"FAIL ({len(errs)})"
        print(f"{f.stem:<11} rows={n:<4} {dict(conf)}  {status}")
        for e in errs[:15]:
            print("   ", e)
        if len(errs) > 15:
            print(f"    ... {len(errs) - 15} more")
    missing = sorted(LENDERS - {f.stem for f in RULES.glob('*.csv')})
    print(f"\nTOTAL rows={total_rows} {dict(grand)} errors={total_err}")
    if missing:
        print("lenders without a rules file:", ", ".join(missing))
    return 1 if total_err or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
