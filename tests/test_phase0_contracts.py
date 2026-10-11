"""Phase 0 gate: data contracts.

Every CSV in data/ loads into its model with no validation errors; rule ids are unique;
every variable is in the controlled vocabulary; every published row's source_file exists;
and the Applicant schema accepts/rejects the right things.
"""
from __future__ import annotations

import csv

import pytest

from eligibility import paths
from eligibility.schema import Applicant, Rule
from eligibility.schema import LENDERS

# the controlled vocabulary (kept in sync with scripts/verify_rules.py)
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
    "bounce_charge", "lending_entity", "bureau_reject_signal", "income_mode",
}


def _rows() -> list[dict]:
    with paths.RULES_LONG.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_data_files_exist():
    missing = [name for name, ok in paths.exists_report().items() if not ok]
    assert not missing, f"missing data files: {missing}"


def test_rules_long_loads_into_model():
    rows = _rows()
    assert len(rows) > 1000, "rule table unexpectedly small"
    bad = []
    for r in rows:
        try:
            Rule(**r)
        except Exception as exc:  # noqa: BLE001
            bad.append((r.get("rule_id"), str(exc)))
    assert not bad, f"{len(bad)} rows failed Rule validation; first: {bad[:3]}"


def test_rule_ids_unique():
    ids = [r["rule_id"] for r in _rows()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate rule_id(s): {sorted(dupes)[:10]}"


def test_every_variable_in_vocabulary():
    unknown = {r["variable"] for r in _rows()} - VARIABLES
    assert not unknown, f"variables not in controlled vocabulary: {unknown}"


def test_every_lender_present():
    seen = {r["lender_id"] for r in _rows()}
    assert seen == set(LENDERS), f"lender set mismatch: missing {set(LENDERS) - seen}, extra {seen - set(LENDERS)}"


def test_published_rows_have_existing_source_file():
    missing = set()
    for r in _rows():
        if r["confidence"] in ("published", "published_conflict"):
            name = r["source_file"]
            if not name:
                missing.add((r["rule_id"], "<empty>"))
                continue
            p = paths.SOURCES / name
            if not p.exists() and p.suffix == ".pdf":
                p = p.with_suffix(".txt")
            if not p.exists():
                missing.add((r["rule_id"], name))
    assert not missing, f"{len(missing)} published rows reference a missing snapshot; first: {sorted(missing)[:5]}"


def test_estimated_rows_have_method_and_no_quote():
    bad = []
    for r in _rows():
        if r["confidence"] in ("derived", "estimated") and not r["estimation_method"].strip():
            bad.append((r["rule_id"], "missing estimation_method"))
        if r["confidence"] == "estimated" and r["quote"].strip():
            bad.append((r["rule_id"], "estimated row has a quote"))
    assert not bad, f"estimation-method/quote problems; first: {bad[:5]}"


# --------------------------------------------------------------------------- applicant schema
def _base_applicant(**over):
    kw = dict(
        employment_type="salaried",
        net_monthly_income=60000,
        date_of_birth="1990-01-01",
        application_date="2026-01-01",
    )
    kw.update(over)
    return Applicant(**kw)


def test_applicant_minimal_valid():
    a = _base_applicant()
    assert 35 < a.age_at_application < 37
    assert a.is_ntc is True  # no bureau_score given


def test_applicant_rejects_zero_score():
    with pytest.raises(Exception):
        _base_applicant(bureau_score=0)


def test_applicant_rejects_out_of_range_score():
    with pytest.raises(Exception):
        _base_applicant(bureau_score=250)


def test_applicant_rejects_future_dob():
    with pytest.raises(Exception):
        _base_applicant(date_of_birth="2027-01-01")


def test_applicant_rejects_unknown_salary_lender():
    with pytest.raises(Exception):
        _base_applicant(salary_account_with_lender="hsbc")


def test_applicant_ntc_vs_zero_distinction():
    a = _base_applicant(bureau_score=760)
    assert a.is_ntc is False
    assert a.bureau_score == 760


def test_applicant_existing_emi_defaults_zero_but_score_stays_none():
    a = _base_applicant()
    assert a.existing_emi_monthly == 0
    assert a.bureau_score is None  # NOT coerced to 0
