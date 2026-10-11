"""Phase 5 gate: pricing + APR + ranking."""
from __future__ import annotations

import pytest

from eligibility import pricing as pr
from eligibility.finance import emi
from eligibility.rules import get_store


@pytest.fixture(scope="module")
def store():
    return get_store()


# --------------------------------------------------------------------------- APR properties
def test_apr_ge_nominal_when_fee_exists():
    a = pr.apr(amount=1_000_000, nominal_pa=12.0, months=60, fee_incl_gst=20_000)
    assert a >= 12.0


def test_apr_equals_nominal_when_no_fee():
    a = pr.apr(amount=1_000_000, nominal_pa=12.0, months=60, fee_incl_gst=0.0)
    assert a == pytest.approx(12.0, abs=0.02)


def test_apr_matches_hand_irr():
    # amount 100000, 12% nominal, 12m, fee 2000. EMI from the standard formula.
    amount, rate, n, fee = 100_000, 12.0, 12, 2_000.0
    e = emi(amount, rate, n)
    net = amount - fee
    # brute-force the monthly IRR
    import numpy as np
    best, berr = None, 1e18
    for i in np.linspace(0.0001, 0.05, 50000):
        val = e * (1 - (1 + i) ** -n) / i
        err = abs(val - net)
        if err < berr:
            berr, best = err, i
    hand = best * 1200
    assert pr.apr(amount, rate, n, fee) == pytest.approx(hand, abs=0.05)


def test_apr_higher_fee_higher_apr():
    low = pr.apr(1_000_000, 12.0, 60, 10_000)
    high = pr.apr(1_000_000, 12.0, 60, 40_000)
    assert high > low


# --------------------------------------------------------------------------- rate band ladder
def test_rate_monotone_across_bands(store):
    rates = [pr.nominal_rate(store, "hdfc", "hdfc_xpress_personal_loan", "salaried", b)[0]
             for b in [">=800", "750-799", "700-749", "650-699", "<650"]]
    assert rates == sorted(rates), f"rate ladder not monotone: {rates}"


def test_best_band_gets_min_rate(store):
    lo, hi = pr.rate_bounds(store, "hdfc", "hdfc_xpress_personal_loan", "salaried")
    r_best, _ = pr.nominal_rate(store, "hdfc", "hdfc_xpress_personal_loan", "salaried", ">=800")
    assert r_best == pytest.approx(lo, abs=0.01)


# --------------------------------------------------------------------------- processing fee + GST
def test_processing_fee_includes_gst(store):
    # SBI: 1.5% min 1000 max 15000, +GST
    fee = pr.processing_fee(store, "sbi", "sbi_personal_loan_salary_package", "salaried", 1_000_000)
    # 1.5% of 10L = 15000, clamped to max 15000, +18% GST = 17700
    assert fee == pytest.approx(17_700, abs=1.0)


def test_hdfc_flat_fee_with_gst(store):
    fee = pr.processing_fee(store, "hdfc", "hdfc_xpress_personal_loan", "salaried", 500_000)
    # flat 6500 + 18% = 7670
    assert fee == pytest.approx(7_670, abs=1.0)


# --------------------------------------------------------------------------- bureau repricing
def test_nbfc_reprice_adds_3pp(store):
    base = pr.price(store, "bajaj", "bajaj_personal_loan", "salaried", "750-799", 500_000, 60)
    rep = pr.price(store, "bajaj", "bajaj_personal_loan", "salaried", "750-799", 500_000, 60,
                   bureau_soft_flags=["reprice_nbfc"])
    assert rep.nominal_rate_pa == pytest.approx(base.nominal_rate_pa + 3.0, abs=0.01)
    assert rep.repriced is True


def test_fintech_reprice_adds_5pp(store):
    base = pr.price(store, "navi", "navi_cash_loan", "all", "700-749", 300_000, 48)
    rep = pr.price(store, "navi", "navi_cash_loan", "all", "700-749", 300_000, 48,
                   bureau_soft_flags=["reprice_fintech"])
    assert rep.nominal_rate_pa == pytest.approx(base.nominal_rate_pa + 5.0, abs=0.01)


# --------------------------------------------------------------------------- women's concession
def test_women_concession_never_raises_rate(store):
    base = pr.nominal_rate(store, "union", "union_women_professional", "salaried", "750-799")[0]
    fem = pr.nominal_rate(store, "union", "union_women_professional", "salaried", "750-799",
                          is_female=True)[0]
    assert fem <= base


def test_women_concession_absent_lender_no_change(store):
    base = pr.nominal_rate(store, "hdfc", "hdfc_xpress_personal_loan", "salaried", "750-799")[0]
    fem = pr.nominal_rate(store, "hdfc", "hdfc_xpress_personal_loan", "salaried", "750-799",
                          is_female=True)[0]
    assert fem == base


# --------------------------------------------------------------------------- determinism
def test_pricing_deterministic(store):
    r1 = pr.price(store, "sbi", "sbi_personal_loan_salary_package", "salaried", "750-799", 800_000, 60)
    r2 = pr.price(store, "sbi", "sbi_personal_loan_salary_package", "salaried", "750-799", 800_000, 60)
    assert r1 == r2


# --------------------------------------------------------------------------- effective-dated fee waiver (§7)
import datetime as _dt


def test_canara_waiver_applied_in_window(store):
    # canara-023: 50% processing-fee waiver for applications between 2026-10-01 and 2026-12-31
    inside = _dt.date(2026, 11, 15)
    frac, note = pr.fee_waiver(store, "canara", "canara_budget", "salaried", inside)
    assert frac == pytest.approx(0.5)
    assert note


def test_canara_waiver_not_applied_after_expiry(store):
    after = _dt.date(2027, 1, 15)
    frac, _ = pr.fee_waiver(store, "canara", "canara_budget", "salaried", after)
    assert frac == 0.0


def test_canara_waiver_not_applied_before_effective(store):
    before = _dt.date(2026, 9, 1)
    frac, _ = pr.fee_waiver(store, "canara", "canara_budget", "salaried", before)
    assert frac == 0.0


def test_waiver_reduces_fee_in_window(store):
    base, _ = pr.price_full(store, "canara", "canara_budget", "salaried", "750-799",
                            500_000, 60, application_date=_dt.date(2027, 6, 1))
    waived, _ = pr.price_full(store, "canara", "canara_budget", "salaried", "750-799",
                              500_000, 60, application_date=_dt.date(2026, 11, 15))
    assert waived.processing_fee < base.processing_fee
