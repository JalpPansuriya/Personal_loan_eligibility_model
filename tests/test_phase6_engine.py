"""Phase 6 gate: engine orchestration, strength score, counterfactual advice."""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility.counterfactual import suggest
from eligibility.engine import Engine
from eligibility.schema import Applicant, Gender, Status


@pytest.fixture(scope="module")
def engine():
    return Engine()


def mk(**over) -> Applicant:
    kw = dict(employment_type="salaried", net_monthly_income=120000, existing_emi_monthly=15000,
              bureau_score=800, total_experience_months=120, current_job_tenure_months=60,
              employer_category="mnc", city="Mumbai",
              date_of_birth=dt.date(1994, 1, 1), application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


# --------------------------------------------------------------------------- run shape
def test_run_returns_offer_per_lender(engine):
    d = engine.run(mk())
    assert len(d.offers) == 20
    assert d.eligible is True


def test_best_offer_has_lowest_apr_among_covering(engine):
    d = engine.run(mk(requested_amount=500_000))
    covering = [o for o in d.offers if o.status.is_offer and (o.max_eligible.amount or 0) >= 499_000]
    assert d.best_offer is not None
    assert d.best_offer.pricing.apr_pa == min(o.pricing.apr_pa for o in covering)


def test_sbi_rejects_without_salary_account(engine):
    d = engine.run(mk())
    sbi = next(o for o in d.offers if o.lender_id == "sbi")
    assert sbi.status == Status.NOT_ELIGIBLE
    assert any(r.code == "SALARY_ACCOUNT_REQUIRED" for r in sbi.reasons)


def test_reasons_carry_source_and_confidence(engine):
    d = engine.run(mk(bureau_score=600))   # fails score at several banks
    rejects = [o for o in d.offers if o.status == Status.NOT_ELIGIBLE and o.reasons]
    assert rejects
    r = rejects[0].reasons[0]
    assert r.rule_id and r.confidence is not None
    assert r.rule_status is not None


# --------------------------------------------------------------------------- determinism
def test_run_is_deterministic(engine):
    a = mk(requested_amount=600_000)
    d1 = engine.run(a)
    d2 = engine.run(a)
    assert [(o.lender_id, o.status, o.max_eligible.amount, o.pricing.apr_pa) for o in d1.offers] == \
           [(o.lender_id, o.status, o.max_eligible.amount, o.pricing.apr_pa) for o in d2.offers]


# --------------------------------------------------------------------------- requested not covered
def test_high_request_not_supported(engine):
    d = engine.run(mk(net_monthly_income=60000, requested_amount=20_000_000))
    eligible = [o for o in d.offers if o.status.is_offer]
    assert eligible
    # none can cover a 2cr request, so requested_supported must be False where there is an offer
    assert any(o.requested_supported is False for o in eligible)


def test_ineligible_profile_lists_blocking_reasons(engine):
    # write-off everywhere -> banks reject, strong blocking reasons surface
    d = engine.run(mk(writeoff_or_settled_24m=True, bureau_score=680))
    if not d.eligible:
        assert d.top_blocking_reasons


# --------------------------------------------------------------------------- strength score bounds
def test_strength_scores_in_range(engine):
    d = engine.run(mk())
    for o in d.offers:
        if o.strength_score is not None:
            assert 0 <= o.strength_score <= 100


def test_strength_invariant_to_requested_amount_when_covered(engine):
    # for an applicant whose max loan comfortably covers both requests, strength should be stable
    base = engine.run(mk(requested_amount=300_000))
    more = engine.run(mk(requested_amount=400_000))
    b = {o.lender_id: o.strength_score for o in base.offers if o.status.is_offer}
    m = {o.lender_id: o.strength_score for o in more.offers if o.status.is_offer}
    common = set(b) & set(m)
    stable = sum(1 for k in common if abs(b[k] - m[k]) <= 1)
    assert stable >= 0.8 * len(common)


# --------------------------------------------------------------------------- gates always win
def test_strength_never_overrides_gate(engine):
    # a profile that fails HDFC score must be NOT_ELIGIBLE regardless of an otherwise strong profile
    d = engine.run(mk(bureau_score=600))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.NOT_ELIGIBLE
    assert hdfc.strength_score is None


# --------------------------------------------------------------------------- counterfactuals
def test_counterfactual_emi_reduction_verified(engine):
    # heavy EMI -> some lender rejects on affordability/amount; fix must actually flip it
    app = mk(net_monthly_income=80000, existing_emi_monthly=60000, requested_amount=500_000)
    d = engine.run(app)
    rejected = [o for o in d.offers if o.status == Status.NOT_ELIGIBLE and
                any(r.code in ("AMOUNT_BELOW_MIN", "FOIR_EXCEEDED") for r in o.reasons)]
    for o in rejected[:3]:
        fixes = suggest(engine, app, o)
        emi_fix = next((f for f in fixes if f.lever == "emi_reduction"), None)
        if emi_fix:
            fixed = app.model_copy(update={"existing_emi_monthly": app.existing_emi_monthly - emi_fix.amount})
            off = engine.evaluate_product(fixed, o.lender_id, o.product, o.segment)
            assert off.status.is_offer


def test_counterfactual_income_increase_verified(engine):
    app = mk(net_monthly_income=12000, bureau_score=760, city="Mumbai")
    d = engine.run(app)
    # pick a lender whose ONLY block is income (not employer/segment), so income can fix it
    rejected = [o for o in d.offers if o.status == Status.NOT_ELIGIBLE and
                {r.code for r in o.reasons} == {"INCOME_BELOW_MIN"}]
    assert rejected
    o = rejected[0]
    fixes = suggest(engine, app, o)
    inc = next((f for f in fixes if f.lever == "income_increase"), None)
    assert inc is not None
    fixed = app.model_copy(update={"net_monthly_income": app.net_monthly_income + inc.amount,
                                   "requested_amount": None})
    off = engine.evaluate_product(fixed, o.lender_id, o.product, o.segment)
    assert off.status.is_offer


def test_counterfactual_non_actionable_explained_not_suggested(engine):
    # self-employed at HDFC (segment not offered) -> explain, no false fix
    app = mk(employment_type="sep", business_vintage_months=60, itr_years_filed=3,
             itr_income_y1=3_000_000, profession="doctor")
    d = engine.run(app)
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    fixes = suggest(engine, app, hdfc)
    assert all(f.lever == "explain" for f in fixes)


def test_counterfactual_wait_months_for_experience(engine):
    app = mk(current_job_tenure_months=1, total_experience_months=3, requested_amount=300_000)
    d = engine.run(app)
    rejected = [o for o in d.offers if o.status == Status.NOT_ELIGIBLE and
                any(r.code in ("EXP_CURRENT_LT_MIN", "EXP_TOTAL_LT_MIN") for r in o.reasons)]
    assert rejected
    fixes = suggest(engine, app, rejected[0])
    wait = next((f for f in fixes if f.lever == "wait_months"), None)
    if wait:
        fixed = app.model_copy(update={
            "total_experience_months": app.total_experience_months + int(wait.amount),
            "current_job_tenure_months": app.current_job_tenure_months + int(wait.amount),
        })
        off = engine.evaluate_product(fixed, rejected[0].lender_id, rejected[0].product, rejected[0].segment)
        assert off.status.is_offer
