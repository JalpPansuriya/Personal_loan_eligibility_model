"""plan3 regression tests (cases A-F).

Each test encodes the CORRECT post-fix behaviour and is expected to fail until the matching
phase lands. Financial figures are checked against INDEPENDENT reference calculations.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant, Status

EDGE = Path(__file__).resolve().parent / "edge_profiles"


@pytest.fixture(scope="module")
def engine():
    return Engine()


def applicant(pid: str, **over) -> Applicant:
    raw = dict(json.loads((EDGE / f"{pid}.json").read_text(encoding="utf-8")))
    raw.pop("profile_id", None)
    raw.pop("description", None)
    raw.update(over)
    return Applicant(**raw)


def ref_emi(p: float, annual_pct: float, n: int) -> float:
    r = annual_pct / 1200.0
    if r == 0:
        return p / n
    f = (1 + r) ** n
    return p * r * f / (f - 1)


# =========================================================== Case A: high-EMI affordability
def test_case_a_canara_max_not_inflated_by_gross_or_card(engine):
    # EDGE03: net 100k, existing EMI 55k, card 50k (payment unknown). The Canara max must not
    # rest on a net->gross inflation + 5%-of-card obligation; such a max must be flagged
    # indicative, and the take-home floor must be computed on NET income.
    d = engine.run(applicant("EDGE03"))
    canara = next(o for o in d.offers if o.lender_id == "canara")
    if canara.status.is_offer and canara.max_eligible.amount:
        # if the max rests on estimated inputs it must be flagged, not presented as verified
        if canara.caps.binding_cap in ("foir", "take_home", "multiple"):
            assert any(r.code in ("MAX_AMOUNT_ESTIMATED", "CARD_PAYMENT_UNKNOWN",
                                  "GROSS_INCOME_ESTIMATED") for r in canara.reasons)


def test_case_a_take_home_floor_uses_net(engine):
    d = engine.run(applicant("EDGE03"))
    canara = next(o for o in d.offers if o.lender_id == "canara")
    # with 55k existing EMI on 100k NET income, take-home room is tight; the FOIR/take-home
    # max must not exceed what 100k net (not 133k gross) can service
    if canara.max_eligible.amount and canara.caps.binding_cap in ("foir", "take_home"):
        assert canara.max_eligible.amount <= 2_600_000


# =========================================================== Case B: no rate above published range
def test_case_b_rate_not_above_published_range(engine):
    d = engine.run(applicant("EDGE02"))  # score 640, DPD 60, 9 enquiries -> reprice pressure
    for o in d.offers:
        p = o.pricing
        if o.status.is_offer and p.rate_max_pa is not None and p.nominal_rate_pa is not None:
            assert p.nominal_rate_pa <= p.rate_max_pa + 0.01, (
                f"{o.lender_id} rate {p.nominal_rate_pa} exceeds published max {p.rate_max_pa}")


def test_case_b_kreditbee_clamped_and_flagged(engine):
    d = engine.run(applicant("EDGE02"))
    kb = next(o for o in d.offers if o.lender_id == "kreditbee")
    if kb.status.is_offer:
        assert kb.pricing.nominal_rate_pa <= 27.5 + 0.01
        assert any(r.code == "RATE_AT_RANGE_CEILING" for r in kb.reasons)


# =========================================================== Case C: product-specific info must be present
def test_case_c_union_women_needs_gender(engine):
    # EDGE07 (doctor) has no gender field -> Union Women Professional must NOT be a match
    d = engine.run(applicant("EDGE07"))
    uwp = next((o for o in d.offers if o.product == "union_women_professional"), None)
    if uwp is not None:
        assert uwp.status != Status.ELIGIBLE_FOR_REQUESTED_TERMS
        assert uwp.status in (Status.ADDITIONAL_INFORMATION_REQUIRED, Status.NOT_ELIGIBLE)


def test_case_c_profession_required_not_inferred(engine):
    # EDGE07 has no structured profession -> doctor/professional products must ask for it,
    # not infer "doctor" from the description
    d = engine.run(applicant("EDGE07"))
    prof_products = [o for o in d.offers if "professional" in o.product]
    for o in prof_products:
        if o.status.is_offer:
            # if it is an offer, profession must have been supplied; here it wasn't
            assert False, f"{o.product} matched without a profession field"


def test_case_c_profession_supplied_allows_match(engine):
    d = engine.run(applicant("EDGE07", profession="doctor", gender="female"))
    # with profession+gender supplied, at least one professional product should screen in
    assert any("professional" in o.product and o.status.is_offer for o in d.offers)


# =========================================================== Case D: card outstanding vs payment
def test_case_d_card_payment_unknown_flagged(engine):
    # EDGE03 has card_outstanding 50k but no card_monthly_payment -> flag, don't impute
    d = engine.run(applicant("EDGE03"))
    offers = [o for o in d.offers if o.status.is_offer]
    assert offers
    assert all(any(r.code == "CARD_PAYMENT_UNKNOWN" for r in o.reasons) for o in offers[:3])


def test_case_d_card_payment_used_when_given(engine):
    # supplying card_monthly_payment removes the unknown flag
    d = engine.run(applicant("EDGE03", card_monthly_payment=2000))
    offers = [o for o in d.offers if o.status.is_offer]
    assert offers
    assert not any(r.code == "CARD_PAYMENT_UNKNOWN" for o in offers for r in o.reasons)


# =========================================================== Case E: settlement -> review not reject
def test_case_e_settlement_review_not_reject(engine):
    # EDGE10: score 720, settled 18m ago, no write-off. Estimated bureau policy must route to
    # MANUAL_REVIEW, not a fabricated NOT_ELIGIBLE (no lender publishes this rule).
    d = engine.run(applicant("EDGE10"))
    reviewed = [o for o in d.offers if o.status == Status.MANUAL_REVIEW]
    rejected_settle = [o for o in d.offers if o.status == Status.NOT_ELIGIBLE
                       and any(r.code == "PRIOR_WRITEOFF_SETTLEMENT" for r in o.reasons)]
    assert reviewed, "settlement should route some lenders to MANUAL_REVIEW"
    assert not rejected_settle, "estimated settlement rule must not hard-reject"


def test_case_e_writeoff_still_rejects(engine):
    # a real write-off is still a hard reject at banks
    d = engine.run(applicant("EDGE10", has_settled_loan=False, settled_loan_months_ago=None,
                             write_off_flag=True))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.NOT_ELIGIBLE
    assert any(r.code == "PRIOR_WRITEOFF_SETTLEMENT" for r in hdfc.reasons)


# =========================================================== Case F: established invariants hold
def test_case_f_age_completed_years():
    a = applicant("EDGE04")  # born 1999-01-02, applying 2026-10-11
    assert a.age_completed_years == 27


def test_case_f_tenure_and_experience_unchanged():
    a = applicant("EDGE04")
    assert a.current_job_tenure_months == 4
    assert a.total_experience_months == 36


def test_case_f_itr_missing_not_zero():
    a = applicant("EDGE01")
    assert a.itr_years_filed is None


def test_case_f_requested_tenure_separate(engine):
    d = engine.run(applicant("EDGE06"))  # 57yo, 60m
    for o in d.offers:
        if o.requested.tenure_months is not None:
            assert o.requested.tenure_months == 60


def test_case_f_requested_emi_matches_requested_principal(engine):
    d = engine.run(applicant("EDGE01"))
    for o in d.offers:
        q = o.requested
        if q.amount and q.tenure_months and q.emi and o.pricing.nominal_rate_pa:
            assert abs(ref_emi(q.amount, o.pricing.nominal_rate_pa, q.tenure_months) - q.emi) <= 2.0
