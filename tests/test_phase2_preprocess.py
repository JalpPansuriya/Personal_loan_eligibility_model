"""Phase 2 gate: preprocessing + finance primitives.

Hand-calculated unit tests per derived feature, boundary cases, and Hypothesis
property tests (FOIR non-negative; maturity >= application age; adding EMI never
raises loan capacity; EMI/PV are inverses).
"""
from __future__ import annotations

import datetime as dt

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eligibility import preprocess as pp
from eligibility.finance import emi, pv_annuity, floor_to, monthly_rate
from eligibility.schema import Applicant, EmploymentType


def mk(**over) -> Applicant:
    kw = dict(
        employment_type="salaried",
        net_monthly_income=100000,
        date_of_birth=dt.date(1994, 1, 1),
        application_date=dt.date(2026, 1, 1),
    )
    kw.update(over)
    return Applicant(**kw)


# --------------------------------------------------------------------------- finance primitives
def test_emi_known_value():
    # 10 lakh @ 12% for 12 months -> 88,849 (standard)
    assert emi(1_000_000, 12, 12) == pytest.approx(88_848.79, abs=1.0)


def test_emi_zero_rate():
    assert emi(120000, 0, 12) == pytest.approx(10000)


def test_emi_pv_are_inverse():
    principal = 777_000
    for rate in (9.5, 12.0, 18.0):
        for n in (12, 36, 60, 84):
            e = emi(principal, rate, n)
            assert pv_annuity(e, rate, n) == pytest.approx(principal, rel=1e-6)


def test_pv_zero_payment():
    assert pv_annuity(0, 12, 60) == 0.0


def test_floor_to():
    assert floor_to(518_234, 10_000) == 510_000
    assert floor_to(49_999, 10_000) == 40_000
    assert floor_to(123_456, 1_000) == 123_000


def test_monthly_rate():
    assert monthly_rate(12) == pytest.approx(0.01)


# --------------------------------------------------------------------------- score band (F31)
@pytest.mark.parametrize("score,band", [
    (None, "NTC"), (820, ">=800"), (800, ">=800"), (799, "750-799"), (750, "750-799"),
    (749, "700-749"), (700, "700-749"), (699, "650-699"), (650, "650-699"), (649, "<650"), (300, "<650"),
])
def test_score_band(score, band):
    assert pp.score_band(score) == band


# --------------------------------------------------------------------------- obligations (F27)
def test_obligations_emi_plus_card_load():
    a = mk(existing_emi_monthly=20000, credit_card_outstanding=100000)
    assert pp.obligations(a) == pytest.approx(20000 + 5000)  # 5% of 1,00,000


def test_obligations_zero_when_no_debt():
    assert pp.obligations(mk()) == 0.0


# --------------------------------------------------------------------------- assessed income (F26)
def test_assessed_income_salaried_net_lender():
    inc, mode = pp.assessed_income(mk(net_monthly_income=80000), "hdfc")
    assert mode == "net" and inc == 80000


def test_assessed_income_gross_lender_converts_up():
    inc, mode = pp.assessed_income(mk(net_monthly_income=75000), "bob")
    assert mode == "gross" and inc == pytest.approx(100000)  # 75000 / 0.75


def test_assessed_income_self_employed_uses_itr():
    a = mk(employment_type="sep", itr_income_y1=2_400_000, net_monthly_income=50000)
    inc, mode = pp.assessed_income(a, "icici")
    assert mode == "itr" and inc == pytest.approx(200000)   # 24L / 12


def test_assessed_income_self_employed_no_itr_falls_back():
    a = mk(employment_type="seb", net_monthly_income=60000)
    inc, mode = pp.assessed_income(a, "icici")
    assert mode == "net" and inc == 60000


# --------------------------------------------------------------------------- itr growth (F33)
def test_itr_growth_two_years():
    a = mk(employment_type="sep", itr_income_y1=1_200_000, itr_income_y2=1_000_000)
    assert pp.itr_growth(a) == pytest.approx(0.2)


def test_itr_growth_none_with_one_itr():
    a = mk(employment_type="sep", itr_income_y1=1_200_000)
    assert pp.itr_growth(a) is None


# --------------------------------------------------------------------------- bureau clean (F32)
def test_bureau_clean_true_for_no_history():
    assert pp.bureau_clean(mk()) is True


def test_bureau_clean_false_on_dpd():
    assert pp.bureau_clean(mk(bureau_score=720, max_dpd_last_12m=45)) is False


def test_bureau_clean_true_on_small_dpd():
    assert pp.bureau_clean(mk(bureau_score=720, max_dpd_last_12m=15)) is True


def test_bureau_clean_false_on_writeoff():
    assert pp.bureau_clean(mk(bureau_score=760, writeoff_or_settled_24m=True)) is False


# --------------------------------------------------------------------------- tenure cap (F25)
def test_max_tenure_by_age_binds_on_maturity():
    # age 58, cap 60y, product max 84m -> only 24m fits
    assert pp.max_tenure_by_age(58.0, 60, 84) == 24


def test_max_tenure_by_age_binds_on_product():
    assert pp.max_tenure_by_age(30.0, 60, 84) == 84


def test_max_tenure_by_age_zero_past_cap():
    assert pp.max_tenure_by_age(61.0, 60, 84) == 0


# --------------------------------------------------------------------------- derive() integration
def test_derive_basic():
    a = mk(net_monthly_income=100000, existing_emi_monthly=20000, bureau_score=780)
    d = pp.derive(a, "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert d.current_foir == pytest.approx(0.2)
    assert d.score_band == "750-799"
    assert d.bureau_clean is True
    assert 31 < d.age_at_application < 33
    assert d.age_at_maturity(60) == pytest.approx(d.age_at_application + 5)


def test_derive_edge_fresher_21():
    a = mk(date_of_birth=dt.date(2005, 1, 1), net_monthly_income=45000, total_experience_months=8)
    d = pp.derive(a, "union", "union_personal_salaried_pvt", "salaried")
    assert 20.9 < d.age_at_application < 21.1


def test_derive_edge_near_retirement():
    a = mk(date_of_birth=dt.date(1967, 1, 1), net_monthly_income=150000)
    d = pp.derive(a, "sbi", "sbi_personal_loan_salary_package", "salaried")
    assert 58.9 < d.age_at_application < 59.1


# --------------------------------------------------------------------------- property tests
money = st.integers(min_value=10_000, max_value=5_000_000)
emis = st.integers(min_value=0, max_value=2_000_000)


@settings(max_examples=200, deadline=None)
@given(income=money, emi_amt=emis)
def test_foir_never_negative(income, emi_amt):
    a = mk(net_monthly_income=income, existing_emi_monthly=emi_amt)
    d = pp.derive(a, "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert d.current_foir >= 0


@settings(max_examples=200, deadline=None)
@given(income=money, emi_amt=emis)
def test_more_emi_raises_foir(income, emi_amt):
    base = pp.derive(mk(net_monthly_income=income, existing_emi_monthly=emi_amt),
                     "hdfc", "hdfc_xpress_personal_loan", "salaried")
    more = pp.derive(mk(net_monthly_income=income, existing_emi_monthly=emi_amt + 5000),
                     "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert more.current_foir >= base.current_foir


@settings(max_examples=100, deadline=None)
@given(tenure=st.integers(min_value=1, max_value=120))
def test_maturity_never_below_application_age(tenure):
    d = pp.derive(mk(), "hdfc", "hdfc_xpress_personal_loan", "salaried")
    assert d.age_at_maturity(tenure) >= d.age_at_application


@settings(max_examples=150, deadline=None)
@given(payment=st.integers(min_value=1_000, max_value=500_000),
       rate=st.floats(min_value=8.0, max_value=36.0),
       n=st.integers(min_value=6, max_value=108))
def test_pv_monotone_in_payment(payment, rate, n):
    lo = pv_annuity(payment, rate, n)
    hi = pv_annuity(payment + 1000, rate, n)
    assert hi >= lo   # more affordable payment -> never smaller loan
