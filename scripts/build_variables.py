"""Generate data/variables.csv (34 model features) and data/coverage_matrix.csv.

Coverage = for each feature, which lenders have at least one rule row (any confidence other than
'estimated') that reads it. Computed from data/lender_rules_long.csv, so the counts in the report
come from data, not hand-estimates.
Usage: .venv\\Scripts\\python.exe scripts/build_variables.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# id, name, unit, type, origin (A applicant / B bureau / D document / S system), description,
# rule variables that read it (from the controlled vocabulary)
FEATURES = [
    ("F01", "employment_type", "enum", "categorical", "A+D", "salaried | sep (self-employed professional) | seb (self-employed business); selects the rule set", ["segment_offered"]),
    ("F02", "employer_category", "enum", "categorical", "A+D", "govt | psu | defence | listed_mnc | private_large | private_small | other", ["employer_category_allowed"]),
    ("F03", "profession", "enum", "categorical", "A+D", "doctor | ca | cs | cost_accountant | architect | engineer | consultant | other (sep only)", ["profession_allowed"]),
    ("F04", "total_experience_months", "months", "integer", "A+D", "Total work experience at application date", ["exp_total_min_months"]),
    ("F05", "current_job_tenure_months", "months", "integer", "A+D", "Months with current employer (payslips / DOJ)", ["exp_current_min_months"]),
    ("F06", "business_vintage_months", "months", "integer|null", "D", "Months since business/practice start (GST/registration); NULL for salaried", ["business_vintage_min_months", "post_qualification_exp_min_months"]),
    ("F07", "net_monthly_income", "INR/month", "number", "D", "Take-home income after tax and PF (payslip / bank statement)", ["income_min_monthly", "income_min_annual", "household_income_min_monthly", "household_income_min_annual", "income_multiple_max", "foir_max", "take_home_floor"]),
    ("F08", "itr_income_y1", "INR/year", "number|null", "D", "Total income in latest filed ITR; NULL for salaried", ["income_min_annual"]),
    ("F09", "itr_income_y2", "INR/year", "number|null", "D", "Total income in previous ITR; NULL if fewer than 2 filed", ["income_min_annual"]),
    ("F10", "itr_years_filed", "count", "integer", "D", "Number of assessment years with a filed ITR", ["itr_years_min"]),
    ("F11", "existing_emi_monthly", "INR/month", "number", "B", "Sum of EMIs on active loans in bureau report", ["foir_max", "take_home_floor", "income_multiple_max"]),
    ("F12", "credit_card_outstanding", "INR", "number", "B", "Revolving outstanding; monthly load = 5% (estimated) added to obligations", ["foir_max"]),
    ("F13", "bureau_score", "300-900 or NULL", "integer|null", "B", "CIBIL/Experian score; NULL = new to credit (never 0)", ["score_min", "score_preferred", "rate_grid"]),
    ("F14", "credit_history_months", "months or NULL", "integer|null", "B", "Age of oldest trade line; NULL if none", ["ntc_allowed"]),
    ("F15", "max_dpd_last_12m", "days or NULL", "integer|null", "B", "Worst days-past-due in last 12 months; NULL if no history", ["bureau_reject_signal"]),
    ("F16", "enquiries_last_6m", "count", "integer", "B", "Hard enquiries in last 6 months", ["bureau_reject_signal"]),
    ("F17", "writeoff_or_settled_24m", "bool", "boolean", "B", "Any write-off or settlement in last 24 months", ["bureau_reject_signal"]),
    ("F18", "active_unsecured_loans", "count", "integer", "B", "Count of active unsecured trade lines", ["max_active_loans"]),
    ("F19", "city_tier", "1/2/3", "categorical", "A+D", "From data/lookups/city_tier.csv (GoI HRA X/Y/Z); pincode used only for lookup", ["city_serviced", "income_min_monthly"]),
    ("F20", "residence_type", "enum", "categorical", "A+D", "owned | rented | company | parental", ["residence_stability_min_months"]),
    ("F21", "salary_account_with_lender", "lender id or none", "categorical", "A", "Bank where salary is credited", ["salary_account_required", "relationship_min_months", "rate_grid"]),
    ("F22", "requested_tenure_months", "months", "integer|null", "A", "Optional requested tenure", ["tenure_min_months", "tenure_max_months"]),
    ("F23", "age_at_application", "years", "number", "S", "(application_date - DOB)/365.25; never a stored age", ["age_min", "age_max_at_application"]),
    ("F24", "age_at_maturity", "years", "number", "S", "F23 + tenure/12", ["age_max_at_maturity"]),
    ("F25", "max_tenure_by_age_L", "months", "integer", "S", "min(product max tenure, (maturity cap - F23) x 12) per lender", ["age_max_at_maturity", "tenure_max_months"]),
    ("F26", "assessed_income_L", "INR/month", "number", "S", "Income as the lender reads it (net vs gross; SE: latest ITR/12)", ["income_mode", "income_min_monthly"]),
    ("F27", "total_obligations_L", "INR/month", "number", "S", "F11 + 5% x F12", ["foir_max", "take_home_floor"]),
    ("F28", "current_foir", "ratio", "number", "S", "F27 / F26", ["foir_max"]),
    ("F29", "emi_capacity_L", "INR/month", "number", "S", "F26 x foir_limit_L - F27 (or take-home floor rule)", ["foir_max", "take_home_floor"]),
    ("F30", "post_loan_foir", "ratio", "number", "S", "(F27 + EMI of requested loan) / F26", ["foir_max"]),
    ("F31", "score_band", "enum", "categorical", "S", ">=800 | 750-799 | 700-749 | 650-699 | <650 | NTC", ["rate_grid", "score_min"]),
    ("F32", "bureau_clean_flag", "bool", "boolean", "S", "F15 < 30 (or NULL) and not F17", ["bureau_reject_signal"]),
    ("F33", "itr_income_growth", "ratio", "number|null", "S", "(F08 - F09) / F09; NULL if fewer than 2 ITRs", ["itr_years_min"]),
    ("F34", "foir_headroom", "ratio", "number", "S", "foir_limit_L - F30; negative = over limit; drives counterfactual fixes", ["foir_max", "take_home_floor"]),
]
LENDERS = ["sbi", "hdfc", "icici", "axis", "kotak", "bob", "pnb", "canara", "union", "indusind", "idfc", "yes",
           "bajaj", "tata", "abcl", "lnt", "poonawalla", "navi", "kreditbee", "moneyview"]


def main() -> None:
    rules = list(csv.DictReader((DATA / "lender_rules_long.csv").open(encoding="utf-8")))
    uses: dict[str, set] = defaultdict(set)      # rule variable -> lenders (non-estimated)
    uses_any: dict[str, set] = defaultdict(set)  # including estimated
    for r in rules:
        uses_any[r["variable"]].add(r["lender_id"])
        if r["confidence"] != "estimated":
            uses[r["variable"]].add(r["lender_id"])
    # bureau rules are applied to every lender by the tiered policy (estimated) -> count separately
    var_rows, cov_rows = [], []
    for fid, name, unit, typ, origin, desc, rule_vars in FEATURES:
        pub = set().union(*(uses[v] for v in rule_vars)) if rule_vars else set()
        anyc = set().union(*(uses_any[v] for v in rule_vars)) if rule_vars else set()
        var_rows.append({"feature_id": fid, "name": name, "unit": unit, "type": typ, "origin": origin,
                         "description": desc, "rule_variables": "|".join(rule_vars),
                         "lenders_published_or_derived": len(pub), "lenders_any_incl_estimated": len(anyc)})
        cov_rows.append({"feature_id": fid, "name": name, **{l: ("P" if l in pub else "E" if l in anyc else "")
                                                             for l in LENDERS}})
    with (DATA / "variables.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(var_rows[0])); w.writeheader(); w.writerows(var_rows)
    with (DATA / "coverage_matrix.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cov_rows[0])); w.writeheader(); w.writerows(cov_rows)
    print(f"variables.csv: {len(var_rows)} features")
    for v in var_rows:
        print(f"  {v['feature_id']} {v['name']:<28} published/derived at {v['lenders_published_or_derived']:>2}/20, "
              f"any {v['lenders_any_incl_estimated']:>2}/20")


if __name__ == "__main__":
    main()
