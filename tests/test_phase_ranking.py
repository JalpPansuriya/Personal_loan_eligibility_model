"""Phase 9 tests: transparent ranking + redefined rule-fit score (plan2 §9).

  * the primary ranking contains only covering offers with a reliable (published) APR,
    ordered by APR then EMI;
  * offers whose APR rests on an estimated rate appear in a separate indicative list;
  * the best offer covers the exact request when any covering offer exists;
  * the rule-fit score is documented, bounded, never an approval probability, and never
    used to order offers.
"""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility import strength as st
from eligibility.engine import Engine
from eligibility.schema import Applicant, Status


@pytest.fixture(scope="module")
def engine():
    return Engine()


def mk(**over) -> Applicant:
    kw = dict(employment_type="salaried", net_monthly_income=150000, existing_emi_monthly=0,
              bureau_score=800, total_experience_months=120, current_job_tenure_months=60,
              employer_category="mnc", city="Mumbai", requested_amount=500000,
              requested_tenure_months=36,
              date_of_birth=dt.date(1990, 1, 1), application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


def test_primary_ranking_sorted_by_apr(engine):
    d = engine.run(mk())
    aprs = [next(o for o in d.offers if o.lender_id == lid).pricing.apr_pa
            for lid in d.ranked_lender_ids]
    assert aprs == sorted(aprs), f"primary ranking not APR-ordered: {aprs}"


def test_primary_ranking_all_cover_and_reliable(engine):
    d = engine.run(mk())
    for lid in d.ranked_lender_ids:
        o = next(x for x in d.offers if x.lender_id == lid)
        assert o.status.covers_request
        assert o.apr_reliable


def test_indicative_list_disjoint_from_primary(engine):
    d = engine.run(mk())
    assert not (set(d.ranked_lender_ids) & set(d.indicative_lender_ids))


def test_best_offer_in_primary_when_available(engine):
    d = engine.run(mk())
    if d.ranked_lender_ids:
        assert d.best_offer.lender_id == d.ranked_lender_ids[0]


def test_score_method_present_and_not_probability(engine):
    d = engine.run(mk())
    assert d.score_method
    assert "probability" not in d.score_method.lower() or "not an approval probability" in d.score_method.lower()


def test_strength_bounded_and_banded(engine):
    d = engine.run(mk())
    for o in d.offers:
        if o.strength_score is not None:
            assert 0 <= o.strength_score <= 100
            assert o.strength_band in ("strong-fit", "comfortable-fit", "borderline-fit", "weak-but-passing")


def test_strength_not_used_for_ranking(engine):
    # a lender with a higher fit score must NOT outrank a lower-APR lender
    d = engine.run(mk())
    if len(d.ranked_lender_ids) >= 2:
        first = next(o for o in d.offers if o.lender_id == d.ranked_lender_ids[0])
        second = next(o for o in d.offers if o.lender_id == d.ranked_lender_ids[1])
        assert (first.pricing.apr_pa, first.requested.emi or 0) <= (second.pricing.apr_pa, second.requested.emi or 1e18)
