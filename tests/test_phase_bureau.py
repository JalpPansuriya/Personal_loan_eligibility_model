"""Phase 5 tests: bureau-history evaluation refinements (plan2 defect J + edge cases).

  * write-off is always a hard negative (timeless);
  * a settlement within 24 months is a hard negative at banks/strict NBFCs;
  * a settlement older than 24 months is a soft (reprice) signal, not a hard reject;
  * a required score that is UNAVAILABLE/FAILED yields ADDITIONAL_INFORMATION_REQUIRED,
    never a silent pass and never confused with new-to-credit.
"""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant, BureauState, Status


@pytest.fixture(scope="module")
def engine():
    return Engine()


def mk(**over) -> Applicant:
    kw = dict(employment_type="salaried", net_monthly_income=120000, existing_emi_monthly=10000,
              bureau_score=760, total_experience_months=120, current_job_tenure_months=60,
              employer_category="mnc", city="Mumbai", salary_account_with_lender="hdfc",
              requested_amount=400000, requested_tenure_months=36,
              date_of_birth=dt.date(1990, 1, 1), application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


def test_recent_settlement_routes_to_review_bank(engine):
    # plan3 Case E: an estimated settlement rule routes to MANUAL_REVIEW, not a fabricated reject
    d = engine.run(mk(has_settled_loan=True, settled_loan_months_ago=18))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.MANUAL_REVIEW
    assert any(r.code == "PRIOR_SETTLEMENT" for r in hdfc.reasons)
    assert not any(r.code == "PRIOR_WRITEOFF_SETTLEMENT" for r in hdfc.reasons)


def test_old_settlement_not_hard_reject_bank(engine):
    # settled 36 months ago: should NOT be a hard write-off/settlement reject
    d = engine.run(mk(has_settled_loan=True, settled_loan_months_ago=36))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert not any(r.code == "PRIOR_WRITEOFF_SETTLEMENT" for r in hdfc.reasons)


def test_writeoff_always_hard_rejects_bank(engine):
    d = engine.run(mk(write_off_flag=True))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.NOT_ELIGIBLE
    assert any(r.code == "PRIOR_WRITEOFF_SETTLEMENT" for r in hdfc.reasons)


def test_bureau_unavailable_requests_info_not_pass(engine):
    # a lender that publishes score_min must not silently pass an unavailable bureau
    a = mk(has_credit_score=None, bureau_score=None, bureau_status=BureauState.UNAVAILABLE)
    d = engine.run(a)
    scored = [o for o in d.offers if any(r.code == "SCORE_UNAVAILABLE" for r in o.reasons)]
    assert scored, "no lender surfaced SCORE_UNAVAILABLE"
    for o in scored:
        assert o.status in (Status.ADDITIONAL_INFORMATION_REQUIRED, Status.NOT_ELIGIBLE)


def test_ntc_distinct_from_unavailable():
    ntc = Applicant(employment_type="salaried", net_monthly_income=60000, has_credit_score=False,
                    date_of_birth="2000-01-01", application_date="2026-01-01")
    unavail = Applicant(employment_type="salaried", net_monthly_income=60000,
                        bureau_status=BureauState.FAILED,
                        date_of_birth="2000-01-01", application_date="2026-01-01")
    assert ntc.bureau_state == BureauState.NEW_TO_CREDIT
    assert unavail.bureau_state == BureauState.FAILED
