"""plan3 Phase 4: per-rule decision trace + reproducibility (§4, §9C)."""
from __future__ import annotations

import datetime as dt

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant, RuleCheckStatus, Status


@pytest.fixture(scope="module")
def engine():
    return Engine()


def mk(**over) -> Applicant:
    kw = dict(employment_type="salaried", net_monthly_income=120000, existing_emi_monthly=10000,
              bureau_score=760, total_experience_months=120, current_job_tenure_months=60,
              employer_category="mnc", city="Mumbai", salary_account_with="hdfc",
              requested_amount=400000, requested_tenure_months=36,
              date_of_birth=dt.date(1990, 1, 1), application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


def test_every_offer_has_checks(engine):
    d = engine.run(mk())
    # products with any gate rows should carry a non-empty checks trace
    traced = [o for o in d.offers if o.checks]
    assert traced, "no decision traces produced"
    for o in traced:
        for c in o.checks:
            assert c.status in RuleCheckStatus
            assert c.rule_id  # each check cites the rule it came from


def test_failing_check_present_on_reject(engine):
    d = engine.run(mk(bureau_score=600))  # fails score at banks
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    assert hdfc.status == Status.NOT_ELIGIBLE
    fails = [c for c in hdfc.checks if c.status == RuleCheckStatus.FAIL]
    assert any(c.rule == "score_min" for c in fails)


def test_unknown_check_never_pass(engine):
    # SE business, no ITR -> itr_years check must be UNKNOWN, not PASS
    d = engine.run(mk(employment_type="seb", business_vintage_months=36, salary_account_with=None,
                      requested_amount=300000))
    for o in d.offers:
        for c in o.checks:
            if c.rule == "itr_years_min" and c.actual_value is None:
                assert c.status != RuleCheckStatus.PASS


def test_check_source_status_mapped(engine):
    d = engine.run(mk())
    labels = {c.source_status for o in d.offers for c in o.checks}
    assert labels & {"VERIFIED_PUBLISHED", "ESTIMATED", "DERIVED_FROM_PUBLIC_CALCULATOR",
                     "CONFLICT_REQUIRES_REVIEW", "UNKNOWN"}


def test_rule_set_version_recorded_and_stable(engine):
    d1 = engine.run(mk())
    d2 = engine.run(mk())
    assert d1.rule_set_version.startswith("sha256:")
    assert d1.rule_set_version == d2.rule_set_version


def test_reproducible_same_input_same_result(engine):
    a = mk(requested_amount=500000)
    d1 = engine.run(a)
    d2 = engine.run(a)
    sig = lambda d: [(o.lender_id, o.status.value, o.max_eligible.amount, o.pricing.apr_pa) for o in d.offers]
    assert sig(d1) == sig(d2)
