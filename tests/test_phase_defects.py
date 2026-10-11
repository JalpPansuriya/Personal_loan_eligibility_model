"""Phase 1 regression tests for the ten observed defects (prompts/plan2.md, A-J).

Each test encodes the CORRECT behaviour required by plan2, using the canonical
field names it specifies (existing_monthly_emi, card_outstanding, has_credit_score,
salary_account_with, max_dpd_days_last_12_months, enquiries_last_6_months,
itr_years_available, has_settled_loan, settled_loan_months_ago, write_off_flag,
employment_type=self_employed_*). They are expected to FAIL until the matching phase
lands, and to stay green afterwards.

Fixtures: tests/edge_profiles/EDGE01..EDGE10.json (dropped in by the user).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant, Status

EDGE = Path(__file__).resolve().parent / "edge_profiles"


def load(pid: str) -> dict:
    return json.loads((EDGE / f"{pid}.json").read_text(encoding="utf-8"))


def applicant(pid: str) -> Applicant:
    """Build an Applicant straight from the canonical-named profile JSON."""
    raw = dict(load(pid))
    raw.pop("profile_id", None)
    raw.pop("description", None)
    return Applicant(**raw)


@pytest.fixture(scope="module")
def engine():
    return Engine()


# --------------------------------------------------------------------------- schema accepts canonical names
@pytest.mark.parametrize("pid", [f"EDGE{i:02d}" for i in range(1, 11)])
def test_canonical_profiles_parse(pid):
    """Every supplied EDGE profile must be accepted with its plan2 field names."""
    a = applicant(pid)
    assert a is not None


# --------------------------------------------------------------------------- Defect A: existing EMI preserved
def test_defect_a_existing_emi_preserved():
    a = applicant("EDGE03")  # net 100000, existing_monthly_emi 55000, card 50000, score 780
    assert a.existing_emi_monthly == 55000, "existing EMI must survive the input pipeline"


# --------------------------------------------------------------------------- Defect B: card outstanding + salary acct
def test_defect_b_card_outstanding_and_salary_account_preserved():
    a = applicant("EDGE02")  # card_outstanding 300000, salary_account_with hdfc
    assert a.credit_card_outstanding == 300000, "card outstanding must survive"
    assert a.salary_account_with_lender == "hdfc", "salary account relationship must survive"


# --------------------------------------------------------------------------- Defect C: employment tenure unchanged
def test_defect_c_employment_tenure_unchanged():
    a = applicant("EDGE04")  # 4 months current job, 36 total
    assert a.current_job_tenure_months == 4
    assert a.total_experience_months == 36
    b = applicant("EDGE05")  # 8 and 8
    assert b.current_job_tenure_months == 8
    assert b.total_experience_months == 8


# --------------------------------------------------------------------------- Defect D: age (completed years)
def test_defect_d_age_completed_years():
    # EDGE04 born 1999-01-02, applying 2026-10-11 -> 27 completed years (not 28)
    a = applicant("EDGE04")
    assert a.age_completed_years == 27


def test_defect_d_age_before_birthday_not_incremented():
    # born 1996-05-10, applying 2026-10-11 -> had birthday -> 30
    a = applicant("EDGE01")
    assert a.age_completed_years == 30
    # EDGE09 born 1990-12-01, applying 2026-10-11 -> birthday not yet -> 35
    b = applicant("EDGE09")
    assert b.age_completed_years == 35


# --------------------------------------------------------------------------- Defect E: ITR not silently zero
def test_defect_e_itr_missing_vs_zero():
    # EDGE07 provides itr_years_available=3; must be read, not dropped
    a = applicant("EDGE07")
    assert a.itr_years_filed == 3
    # a salaried profile with no ITR field must report ITR as unknown (None), not 0
    salaried = applicant("EDGE01")
    assert salaried.itr_years_filed is None


# --------------------------------------------------------------------------- Defect F: requested tenure preserved
def test_defect_f_requested_tenure_preserved(engine):
    # EDGE06: age 57, requests 60 months. The requested tenure must never be rewritten.
    a = applicant("EDGE06")
    assert a.requested_tenure_months == 60
    d = engine.run(a)
    for o in d.offers:
        if o.requested.tenure_months is not None:
            assert o.requested.tenure_months == 60, (
                f"{o.lender_id} rewrote requested tenure to {o.requested.tenure_months}")


# --------------------------------------------------------------------------- Defect G: requested EMI on requested P
def test_defect_g_requested_emi_uses_requested_principal(engine):
    from eligibility.finance import emi as emi_fn
    a = applicant("EDGE09")  # requests 50L; many products cap lower
    d = engine.run(a)
    for o in d.offers:
        q = o.requested
        if q.amount and q.tenure_months and q.emi and o.pricing.nominal_rate_pa:
            # requested quote's EMI must match EMI(requested principal, rate, requested tenure)
            assert q.amount == a.requested_amount, (
                f"{o.lender_id} requested amount {q.amount} != requested {a.requested_amount}")
            ref = emi_fn(q.amount, o.pricing.nominal_rate_pa, q.tenure_months)
            assert abs(ref - q.emi) <= 2.0


# --------------------------------------------------------------------------- Defect H: coverage vs eligibility
def test_defect_h_uncovered_not_counted_as_covering(engine):
    a = applicant("EDGE09")  # 50L request
    d = engine.run(a)
    for o in d.offers:
        if (o.max_eligible.amount or 0) < (a.requested_amount or 0) - 1:
            assert o.requested_supported is False, (
                f"{o.lender_id} max {o.max_eligible.amount} < request but marked supported")
    # the best option, if any, must actually cover the request (or be clearly alternative)
    if d.best_offer is not None and d.best_offer.requested_supported is False:
        assert d.best_offer.status == Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS


# --------------------------------------------------------------------------- Defect I: no runaway max amount
def test_defect_i_canara_capped(engine):
    a = applicant("EDGE09")  # high income, could trigger 25x multiple
    d = engine.run(a)
    canara = next((o for o in d.offers if o.lender_id == "canara"), None)
    if canara and canara.max_eligible.amount:
        # Canara Budget publishes 50L (prime) / 40L (delight) ceilings
        assert canara.max_eligible.amount <= 5_000_000, (
            f"Canara max {canara.max_eligible.amount} exceeds its published 50L ceiling")


# --------------------------------------------------------------------------- Defect J: credit-history edge cases read
def test_defect_j_dpd_and_enquiries_block_banks(engine):
    a = applicant("EDGE02")  # score 640, DPD 60, 9 enquiries
    d = engine.run(a)
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.NOT_ELIGIBLE
    codes = {r.code for r in hdfc.reasons}
    assert codes & {"RECENT_DPD_GTE30", "EXCESS_ENQUIRIES", "SCORE_BELOW_MIN"}


def test_defect_j_settled_loan_read(engine):
    a = applicant("EDGE10")  # has_settled_loan 18 months ago, write_off_flag false
    assert a.has_settled_loan is True
    assert a.settled_loan_months_ago == 18
    assert a.write_off_flag is False


def test_defect_j_ntc_missing_score(engine):
    a = applicant("EDGE05")  # has_credit_score false, bureau_score null
    assert a.has_credit_score is False
    assert a.bureau_score is None
    assert a.is_ntc is True
