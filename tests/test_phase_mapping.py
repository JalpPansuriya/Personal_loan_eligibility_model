"""Phase 2 input-contract tests (plan2 §3).

Verifies the canonical Applicant schema:
  * accepts plan2's canonical field names and the documented legacy aliases;
  * preserves every financially-material value through parsing (no silent zeroing);
  * rejects truly unknown keys instead of dropping them;
  * keeps 'missing' distinct from 'zero'/'good' for ITR and bureau;
  * computes completed-years age correctly around birthdays.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eligibility.schema import Applicant, BureauState, EmploymentType

EDGE = Path(__file__).resolve().parent / "edge_profiles"

# fields that must survive JSON -> Applicant unchanged (canonical name -> attribute)
MATERIAL = {
    "net_monthly_income": "net_monthly_income",
    "existing_monthly_emi": "existing_emi_monthly",
    "card_outstanding": "credit_card_outstanding",
    "bureau_score": "bureau_score",
    "total_experience_months": "total_experience_months",
    "current_job_tenure_months": "current_job_tenure_months",
    "business_vintage_months": "business_vintage_months",
    "max_dpd_days_last_12_months": "max_dpd_last_12m",
    "enquiries_last_6_months": "enquiries_last_6m",
    "itr_years_available": "itr_years_filed",
    "requested_amount": "requested_amount",
    "requested_tenure_months": "requested_tenure_months",
    "settled_loan_months_ago": "settled_loan_months_ago",
}


def _profiles():
    for pf in sorted(EDGE.glob("EDGE*.json")):
        raw = json.loads(pf.read_text(encoding="utf-8"))
        yield pf.stem, raw


def _mk(raw: dict) -> Applicant:
    raw = dict(raw)
    raw.pop("profile_id", None)
    raw.pop("description", None)
    return Applicant(**raw)


@pytest.mark.parametrize("pid,raw", list(_profiles()))
def test_material_fields_survive_parsing(pid, raw):
    a = _mk(raw)
    for key, attr in MATERIAL.items():
        if key in raw:
            got = getattr(a, attr)
            assert got == raw[key], f"{pid}: {key} became {got}, expected {raw[key]}"


def test_legacy_aliases_still_accepted():
    a = Applicant(
        employment_type="salaried", net_monthly_income=60000,
        existing_emi_monthly=5000, credit_card_outstanding=20000,
        max_dpd_last_12m=10, enquiries_last_6m=2, salary_account_with_lender="hdfc",
        date_of_birth="1990-01-01", application_date="2026-01-01",
    )
    assert a.existing_emi_monthly == 5000
    assert a.credit_card_outstanding == 20000
    assert a.max_dpd_last_12m == 10
    assert a.salary_account_with_lender == "hdfc"


def test_unknown_key_rejected():
    with pytest.raises(Exception):
        Applicant(
            employment_type="salaried", net_monthly_income=60000,
            date_of_birth="1990-01-01", application_date="2026-01-01",
            annual_bonus=999999,  # not a supported field
        )


def test_self_employed_aliases():
    a = Applicant(employment_type="self_employed_professional", net_monthly_income=100000,
                  date_of_birth="1985-01-01", application_date="2026-01-01")
    assert a.employment_type == EmploymentType.SEP
    b = Applicant(employment_type="self_employed_business", net_monthly_income=100000,
                  date_of_birth="1985-01-01", application_date="2026-01-01")
    assert b.employment_type == EmploymentType.SEB


def test_itr_missing_is_none_not_zero():
    a = Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth="1990-01-01", application_date="2026-01-01")
    assert a.itr_years_filed is None  # unknown, not an established 0


def test_bureau_states_distinct():
    valid = Applicant(employment_type="salaried", net_monthly_income=60000, bureau_score=760,
                      has_credit_score=True, date_of_birth="1990-01-01", application_date="2026-01-01")
    ntc = Applicant(employment_type="salaried", net_monthly_income=60000, has_credit_score=False,
                    date_of_birth="1990-01-01", application_date="2026-01-01")
    unknown = Applicant(employment_type="salaried", net_monthly_income=60000,
                        date_of_birth="1990-01-01", application_date="2026-01-01")
    assert valid.bureau_state == BureauState.VALID
    assert ntc.bureau_state == BureauState.NEW_TO_CREDIT
    assert unknown.bureau_state == BureauState.NEW_TO_CREDIT


def test_contradictory_bureau_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=60000,
                  has_credit_score=False, bureau_score=760,
                  date_of_birth="1990-01-01", application_date="2026-01-01")


@pytest.mark.parametrize("dob,app_date,expected", [
    ("1999-01-02", "2026-10-11", 27),  # birthday passed
    ("1990-12-01", "2026-10-11", 35),  # birthday not yet reached
    ("1996-05-10", "2026-10-11", 30),
    ("2000-10-11", "2026-10-11", 26),  # exactly on birthday
    ("2000-10-12", "2026-10-11", 25),  # one day before birthday
])
def test_completed_years_age(dob, app_date, expected):
    a = Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth=dob, application_date=app_date)
    assert a.age_completed_years == expected


def test_application_date_preserved():
    a = Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth="1990-01-01", application_date="2026-10-11")
    assert a.application_date.isoformat() == "2026-10-11"
