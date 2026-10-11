"""Phase 3 gate: hard-gate evaluation.

Boundary tests per gate variable (at / just below / just above the threshold),
segment-not-offered, NTC handling, the tiered bureau policy, and the stricter-value
conflict policy (Kotak score_min resolves to 750, not 685).
"""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility import preprocess as pp
from eligibility.gates import GateEvaluator
from eligibility.rules import get_store
from eligibility.schema import Applicant


@pytest.fixture(scope="module")
def ev():
    return GateEvaluator(get_store())


def mk(**over) -> Applicant:
    kw = dict(
        employment_type="salaried",
        net_monthly_income=100000,
        bureau_score=780,
        total_experience_months=120,
        current_job_tenure_months=60,
        date_of_birth=dt.date(1990, 1, 1),
        application_date=dt.date(2026, 1, 1),
    )
    kw.update(over)
    return Applicant(**kw)


def gate(ev, app, lender, product, segment):
    d = pp.derive(app, lender, product, segment)
    return ev.evaluate(app, product, segment, lender, d)


def codes(result):
    return {r.code for r in result.reasons + result.missing_info + result.review}


# --------------------------------------------------------------------------- segment offered
def test_hdfc_rejects_self_employed(ev):
    r = gate(ev, mk(employment_type="sep", business_vintage_months=60, itr_years_filed=3,
                    itr_income_y1=2_000_000),
             "hdfc", "hdfc_xpress_personal_loan", "sep")
    assert "SEGMENT_NOT_OFFERED" in codes(r)
    assert r.passed is False


def test_hdfc_accepts_salaried(ev):
    r = gate(ev, mk(net_monthly_income=100000), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert "SEGMENT_NOT_OFFERED" not in codes(r)


# --------------------------------------------------------------------------- income gate boundary (HDFC 25000)
@pytest.mark.parametrize("income,blocked", [(24999, True), (25000, False), (25001, False)])
def test_hdfc_income_boundary(ev, income, blocked):
    r = gate(ev, mk(net_monthly_income=income), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert ("INCOME_BELOW_MIN" in codes(r)) is blocked


# --------------------------------------------------------------------------- score gate boundary (HDFC 720)
@pytest.mark.parametrize("score,blocked", [(719, True), (720, False), (721, False)])
def test_hdfc_score_boundary(ev, score, blocked):
    r = gate(ev, mk(bureau_score=score), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert ("SCORE_BELOW_MIN" in codes(r)) is blocked


# --------------------------------------------------------------------------- age min boundary (SBI 21)
@pytest.mark.parametrize("dob,blocked", [
    (dt.date(2005, 6, 1), True),    # ~20.6y at 2026-01-01
    (dt.date(2004, 12, 1), False),  # ~21.1y
])
def test_age_min_boundary(ev, dob, blocked):
    app = mk(date_of_birth=dob, salary_account_with_lender="sbi",
             employer_category="govt", bureau_score=700, current_job_tenure_months=24)
    r = gate(ev, app, "sbi", "sbi_personal_loan_salary_package", "salaried")
    assert ("AGE_BELOW_MIN" in codes(r)) is blocked


# --------------------------------------------------------------------------- experience boundary (HDFC current 12m)
@pytest.mark.parametrize("tenure,blocked", [(11, True), (12, False)])
def test_hdfc_current_exp_boundary(ev, tenure, blocked):
    r = gate(ev, mk(current_job_tenure_months=tenure), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert ("EXP_CURRENT_LT_MIN" in codes(r)) is blocked


# --------------------------------------------------------------------------- NTC
def test_hdfc_rejects_ntc(ev):
    r = gate(ev, mk(bureau_score=None), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert "NTC_NOT_ALLOWED" in codes(r)


def test_sbi_allows_ntc(ev):
    app = mk(bureau_score=None, salary_account_with_lender="sbi", employer_category="govt",
             net_monthly_income=30000, current_job_tenure_months=24)
    r = gate(ev, app, "sbi", "sbi_personal_loan_salary_package", "salaried")
    assert "NTC_NOT_ALLOWED" not in codes(r)


# --------------------------------------------------------------------------- salary account (SBI)
def test_sbi_requires_salary_account(ev):
    r = gate(ev, mk(employer_category="govt", bureau_score=700, net_monthly_income=30000,
                    current_job_tenure_months=24),
             "sbi", "sbi_personal_loan_salary_package", "salaried")
    assert "SALARY_ACCOUNT_REQUIRED" in codes(r)


def test_sbi_salary_account_present_passes(ev):
    r = gate(ev, mk(salary_account_with_lender="sbi", employer_category="govt", bureau_score=700,
                    net_monthly_income=30000, current_job_tenure_months=24),
             "sbi", "sbi_personal_loan_salary_package", "salaried")
    assert "SALARY_ACCOUNT_REQUIRED" not in codes(r)


# --------------------------------------------------------------------------- missing data fails the gate
def test_missing_vintage_requires_more_info(ev):
    # icici SE needs 24m vintage; None must NOT silently pass -> flagged as missing info
    app = mk(employment_type="seb", business_vintage_months=None, itr_years_filed=3,
             itr_income_y1=3_000_000, total_experience_months=120)
    r = gate(ev, app, "icici", "icici_personal_loan", "seb")
    assert "VINTAGE_LT_MIN_MISSING" in {x.code for x in r.missing_info}
    # and it is not a confirmed violation
    assert "VINTAGE_LT_MIN_MISSING" not in {x.code for x in r.reasons}


# --------------------------------------------------------------------------- tiered bureau policy
def test_bank_rejects_dpd30(ev):
    r = gate(ev, mk(max_dpd_last_12m=30), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert "RECENT_DPD_GTE30" in codes(r)


def test_bank_rejects_6_enquiries(ev):
    r = gate(ev, mk(enquiries_last_6m=6), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert "EXCESS_ENQUIRIES" in codes(r)


def test_bank_rejects_writeoff(ev):
    r = gate(ev, mk(writeoff_or_settled_24m=True), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert "PRIOR_WRITEOFF_SETTLEMENT" in codes(r)


def test_nbfc_dpd30_is_soft_not_reject(ev):
    r = gate(ev, mk(max_dpd_last_12m=30), "bajaj", "bajaj_personal_loan", "salaried")
    assert "RECENT_DPD_GTE30" not in codes(r)
    assert "reprice_nbfc" in r.bureau_soft_flags


def test_nbfc_dpd60_rejects(ev):
    r = gate(ev, mk(max_dpd_last_12m=60), "bajaj", "bajaj_personal_loan", "salaried")
    assert "RECENT_DPD_GTE60" in codes(r)


def test_fintech_kreditbee_lenient_on_dpd(ev):
    r = gate(ev, mk(max_dpd_last_12m=45, bureau_score=640), "kreditbee",
             "kreditbee_personal_loan", "all")
    assert not any(c.startswith("RECENT_DPD") for c in codes(r))
    assert "reprice_fintech" in r.bureau_soft_flags


def test_fintech_navi_rejects_writeoff(ev):
    r = gate(ev, mk(writeoff_or_settled_24m=True, bureau_score=700), "navi", "navi_cash_loan", "all")
    assert "PRIOR_WRITEOFF_SETTLEMENT" in codes(r)


# --------------------------------------------------------------------------- stricter-value conflict
def test_kotak_score_min_resolves_to_750(ev):
    # Kotak publishes 750 and 685 (conflict). Stricter = 750, so a 700 score must fail.
    r = gate(ev, mk(bureau_score=700, employer_category="mnc"), "kotak",
             "kotak_personal_loan", "salaried")
    assert "SCORE_BELOW_MIN" in codes(r)


def test_kotak_score_760_passes(ev):
    r = gate(ev, mk(bureau_score=760, employer_category="mnc", salary_account_with_lender="kotak",
                    net_monthly_income=40000),
             "kotak", "kotak_personal_loan", "salaried")
    assert "SCORE_BELOW_MIN" not in codes(r)


# --------------------------------------------------------------------------- Axis city service
def test_axis_rejects_unlisted_city(ev):
    r = gate(ev, mk(city="Rampur"), "axis", "axis_personal_loan", "salaried")
    assert "CITY_NOT_SERVICED" in codes(r)


def test_axis_accepts_listed_city(ev):
    r = gate(ev, mk(city="Mumbai"), "axis", "axis_personal_loan", "salaried")
    assert "CITY_NOT_SERVICED" not in codes(r)
