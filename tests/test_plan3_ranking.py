"""plan3 Phase 8: four separate ranking categories + insufficient-evidence (§6)."""
from __future__ import annotations

import datetime as dt

import pytest

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


def test_rankings_populated(engine):
    r = engine.run(mk()).rankings
    assert r.basis
    assert r.lowest_estimated_rate is not None
    assert r.lowest_reliable_apr is not None


def test_best_for_requested_covers_exact(engine):
    d = engine.run(mk())
    r = d.rankings
    if r.best_for_requested_terms:
        o = next(x for x in d.offers if x.lender_id == r.best_for_requested_terms)
        assert o.status.covers_request
        assert o.apr_reliable


def test_lowest_rate_vs_lowest_apr_distinct_fields(engine):
    # the lowest advertised rate is NOT necessarily the lowest APR (fees differ); both exist
    d = engine.run(mk())
    r = d.rankings
    assert r.lowest_estimated_rate is not None and r.lowest_reliable_apr is not None


def test_uncovered_request_uses_alternative(engine):
    d = engine.run(mk(net_monthly_income=250000, requested_amount=50_000_000))  # 5cr nobody covers
    r = d.rankings
    assert r.best_for_requested_terms is None
    assert r.best_supported_alternative is not None or r.insufficient_evidence


def test_insufficient_evidence_when_no_eligible(engine):
    # NTC + adverse everywhere -> no eligible offers
    d = engine.run(mk(has_credit_score=False, bureau_score=None, net_monthly_income=9000,
                      requested_amount=100000))
    if not d.eligible:
        assert d.rankings.insufficient_evidence


def test_headline_best_matches_requested_category(engine):
    d = engine.run(mk())
    if d.best_offer and d.rankings.best_for_requested_terms:
        assert d.best_offer.lender_id == d.rankings.best_for_requested_terms
