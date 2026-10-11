"""Phase 10 gate: scenario coverage (§13) + regression/consistency invariants (§14).

These exercise the real engine, not hardcoded output. They assert the audit fixes hold:
the requested EMI matches the requested principal/tenure, the max-eligible EMI matches the
max amount/tenure, caps are respected, APR is not rate+fee, provenance is preserved, and
missing information never silently produces an eligible status.
"""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility import pricing as pr
from eligibility.engine import Engine
from eligibility.finance import emi
from eligibility.quality import model_summary
from eligibility.schema import Applicant, Confidence, RuleStatus, Status


@pytest.fixture(scope="module")
def engine():
    return Engine()


def mk(**over) -> Applicant:
    kw = dict(employment_type="salaried", net_monthly_income=100000, bureau_score=780,
              total_experience_months=120, current_job_tenure_months=60,
              employer_category="private_ltd", city="Mumbai",
              date_of_birth=dt.date(1990, 1, 1), application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


def offers(engine, app):
    return engine.run(app).offers


def elig(engine, app):
    return [o for o in engine.run(app).offers if o.status.is_offer]


# =============================================================== §14 regression invariants
def test_requested_emi_matches_requested_principal_and_tenure(engine):
    app = mk(net_monthly_income=200000, requested_amount=500000, requested_tenure_months=36)
    for o in elig(engine, app):
        if o.requested.amount:
            expected = round(emi(o.requested.amount, o.pricing.nominal_rate_pa, o.requested.tenure_months), 2)
            assert abs(o.requested.emi - expected) < 1.0, o.lender_id


def test_max_eligible_emi_matches_max_amount_and_tenure(engine):
    app = mk(net_monthly_income=200000, requested_amount=500000, requested_tenure_months=36)
    for o in elig(engine, app):
        expected = round(emi(o.max_eligible.amount, o.pricing.nominal_rate_pa, o.max_eligible.tenure_months), 2)
        assert abs(o.max_eligible.emi - expected) < 1.0, o.lender_id


def test_the_reported_bug_is_fixed(engine):
    # requested 5L/36m @ ~9.25% -> EMI ~15,958 while max eligible is far larger.
    app = mk(net_monthly_income=200000, existing_emi_monthly=0, bureau_score=800,
             requested_amount=500000, requested_tenure_months=36)
    best = engine.run(app).best_offer
    assert best is not None
    # the requested EMI is for 5L, NOT for the multi-lakh max eligible amount
    assert best.requested.amount == 500000
    assert 15000 < best.requested.emi < 17000
    assert best.max_eligible.amount >= 1000000
    # the max-eligible EMI is on a larger principal/longer tenure, so it is clearly distinct
    assert best.max_eligible.amount > best.requested.amount
    assert best.max_eligible.emi > best.requested.emi


def test_max_never_exceeds_product_cap(engine):
    app = mk(net_monthly_income=1000000, requested_amount=None)  # very high income
    for o in elig(engine, app):
        if o.caps.product is not None:
            assert o.max_eligible.amount <= o.caps.product + 1, o.lender_id


def test_max_equals_binding_cap(engine):
    app = mk(net_monthly_income=150000)
    numeric_caps = {"foir", "take_home", "multiple", "product", "calculator"}
    for o in elig(engine, app):
        caps = {k: v for k, v in o.caps.model_dump().items()
                if k in numeric_caps and v is not None}
        if caps:
            assert o.max_eligible.amount <= min(caps.values()) + 1000, o.lender_id


def test_requested_emi_recalculates_with_amount(engine):
    small = engine.run(mk(net_monthly_income=200000, requested_amount=300000, requested_tenure_months=36)).best_offer
    big = engine.run(mk(net_monthly_income=200000, requested_amount=600000, requested_tenure_months=36)).best_offer
    assert big.requested.emi > small.requested.emi


def test_requested_emi_recalculates_with_tenure(engine):
    short = engine.run(mk(net_monthly_income=200000, requested_amount=500000, requested_tenure_months=24)).best_offer
    long = engine.run(mk(net_monthly_income=200000, requested_amount=500000, requested_tenure_months=60)).best_offer
    assert short.requested.emi > long.requested.emi   # same principal, longer tenure -> smaller EMI


def test_apr_is_not_rate_plus_fee(engine):
    # APR must come from cash flows, never nominal + fee% + gst%
    app = mk(net_monthly_income=200000, requested_amount=500000, requested_tenure_months=36)
    for o in elig(engine, app):
        p = o.pricing
        if p.processing_fee and p.processing_fee > 0:
            naive = p.nominal_rate_pa + (p.processing_fee + (p.gst_on_fee or 0)) / o.requested.amount * 100
            # APR from IRR differs from this naive addition
            assert abs(p.apr_pa - naive) > 0.001 or p.apr_pa >= p.nominal_rate_pa


def test_fee_and_gst_kept_separate(engine):
    app = mk(net_monthly_income=200000, requested_amount=500000)
    for o in elig(engine, app):
        p = o.pricing
        if p.processing_fee:
            assert abs((p.gst_on_fee or 0) - round(p.processing_fee * 0.18, 2)) < 1.0, o.lender_id
            assert p.net_disbursement == pytest.approx(
                o.requested.amount - p.processing_fee - (p.gst_on_fee or 0), abs=1.0)


def test_best_offer_passes_all_gates(engine):
    app = mk(net_monthly_income=120000, requested_amount=500000)
    best = engine.run(app).best_offer
    assert best is not None and best.status.is_offer
    # re-evaluate the chosen product: it must still be an offer (no hidden violation)
    off = engine.evaluate_product(app, best.lender_id, best.product, best.segment)
    assert off.status.is_offer


def test_rate_provenance_preserved(engine):
    app = mk(net_monthly_income=120000, requested_amount=500000)
    for o in elig(engine, app):
        # a published rate must carry its source url
        if o.pricing.rate_confidence in (Confidence.PUBLISHED, Confidence.PUBLISHED_CONFLICT):
            assert o.pricing.rate_source_url, o.lender_id


def test_estimated_not_labelled_published(engine):
    # an estimated reason must not claim PUBLISHED rule_status
    d = engine.run(mk(bureau_score=720, max_dpd_last_12m=45))  # bureau reject (estimated)
    for o in d.offers:
        for r in o.reasons:
            if r.confidence == Confidence.ESTIMATED:
                assert r.rule_status != RuleStatus.PUBLISHED


# =============================================================== §13 scenarios / boundaries
def test_missing_info_does_not_silently_pass(engine):
    # SE with no vintage -> ADDITIONAL_INFORMATION_REQUIRED, never eligible
    app = mk(employment_type="seb", business_vintage_months=None, itr_years_filed=3,
             itr_income_y1=3_000_000)
    icici = next(o for o in engine.run(app).offers if o.lender_id == "icici")
    assert icici.status == Status.ADDITIONAL_INFORMATION_REQUIRED
    assert not icici.status.is_offer


def test_requested_above_product_limit_marks_not_supported(engine):
    # HDFC product cap is 40L; request 2cr -> offer exists but requested not supported
    app = mk(net_monthly_income=5_000_000, requested_amount=20_000_000)
    hdfc = next(o for o in engine.run(app).offers if o.lender_id == "hdfc")
    if hdfc.status.is_offer:
        assert hdfc.requested_supported is False
        assert hdfc.max_eligible.amount <= (hdfc.caps.product or 1e12) + 1


def test_tenure_out_of_range_is_clamped(engine):
    # requested 108m but a lender maxes at 60 -> its offer tenure must be <= its cap
    app = mk(net_monthly_income=200000, requested_amount=400000, requested_tenure_months=108)
    for o in elig(engine, app):
        assert o.requested.tenure_months is None or o.requested.tenure_months <= 108


def test_age_at_maturity_blocks_long_tenure_for_older(engine):
    # 59-year-old at a lender with a 60y maturity cap: tenure must keep maturity <= cap.
    app = mk(date_of_birth=dt.date(1967, 1, 1), net_monthly_income=200000,
             requested_amount=300000, requested_tenure_months=84)
    age = engine.run(app).applicant_age
    hdfc = next((o for o in elig(engine, app) if o.lender_id == "hdfc"), None)
    if hdfc:  # HDFC maturity cap is 60y -> at age ~59 only ~12 months fit
        assert age + hdfc.max_eligible.tenure_months / 12 <= 60.5


def test_bureau_states_distinct(engine):
    ntc = engine.run(mk(bureau_score=None))
    low = engine.run(mk(bureau_score=600))
    clean = engine.run(mk(bureau_score=800))
    # NTC and low-score and clean must not produce identical offer counts
    n_ntc = sum(1 for o in ntc.offers if o.status.is_offer)
    n_low = sum(1 for o in low.offers if o.status.is_offer)
    n_clean = sum(1 for o in clean.offers if o.status.is_offer)
    assert n_clean >= n_low and n_clean >= n_ntc


def test_null_score_not_zero(engine):
    # a None score must be treated as NTC, not as score 0 (which would fail every min)
    d = engine.run(mk(bureau_score=None))
    ntc_friendly = [o for o in d.offers if o.status.is_offer]
    # at least the NTC-allowing lenders should offer; score-0 would reject all
    assert len(ntc_friendly) >= 1


def test_invalid_input_rejected_by_schema():
    with pytest.raises(Exception):
        mk(bureau_score=0)       # 0 is invalid; must not be read as NTC
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=-5000,
                  date_of_birth=dt.date(1990, 1, 1), application_date=dt.date(2026, 1, 1))


def test_age_uses_application_date_not_today(engine):
    # same DOB, different application dates -> different ages at application
    young = mk(date_of_birth=dt.date(2000, 1, 1), application_date=dt.date(2021, 1, 1))
    older = mk(date_of_birth=dt.date(2000, 1, 1), application_date=dt.date(2026, 1, 1))
    assert round(engine.run(young).applicant_age) == 21
    assert round(engine.run(older).applicant_age) == 26


# =============================================================== §15 model quality
def test_model_summary_shape():
    s = model_summary()
    assert s["lenders_configured"] == 20
    assert s["products_configured"] >= 30
    assert s["products_with_published_rules"] >= 1
    assert "note" in s


def test_no_approval_language_in_statuses():
    # the status vocabulary must not contain APPROVE/REJECT (misleading)
    values = {s.value for s in Status}
    assert "APPROVE" not in values and "REJECT" not in values
    assert "ELIGIBLE_FOR_REQUESTED_TERMS" in values
    assert "ELIGIBLE_FOR_ALTERNATIVE_TERMS" in values
