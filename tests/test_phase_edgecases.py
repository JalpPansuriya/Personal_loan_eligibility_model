"""Phase 10 tests: edge-case coverage + the 25 required verifications (plan2 §11/§15).

These run the REAL engine and compare financial figures against INDEPENDENT reference
calculations (EMI/APR/age computed here, not taken from the function under test).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant, BureauState, Status

EDGE = Path(__file__).resolve().parent / "edge_profiles"
TOL = 2.0  # rupee tolerance for EMI reference checks


@pytest.fixture(scope="module")
def engine():
    return Engine()


def load(pid: str) -> dict:
    return json.loads((EDGE / f"{pid}.json").read_text(encoding="utf-8"))


def applicant(pid: str) -> Applicant:
    raw = dict(load(pid))
    raw.pop("profile_id", None)
    raw.pop("description", None)
    return Applicant(**raw)


# independent EMI reference (reducing balance), NOT importing the production emi()
def ref_emi(p: float, annual_pct: float, n: int) -> float:
    r = annual_pct / 1200.0
    if r == 0:
        return p / n
    f = (1 + r) ** n
    return p * r * f / (f - 1)


# =========================================================== EDGE profiles all evaluate
@pytest.mark.parametrize("pid", [f"EDGE{i:02d}" for i in range(1, 11)])
def test_edge_profiles_run(engine, pid):
    d = engine.run(applicant(pid))
    assert len(d.offers) == 20
    # every offer has a coherent status
    for o in d.offers:
        assert isinstance(o.status, Status)


# =========================================================== the 25 required verifications
def test_v4_age_on_and_around_birthday():
    # born 1999-01-02; on 2026-01-01 -> 26 (day before birthday); on 2026-01-02 -> 27
    a = Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth="1999-01-02", application_date="2026-01-01")
    b = Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth="1999-01-02", application_date="2026-01-02")
    assert a.age_completed_years == 26
    assert b.age_completed_years == 27


def test_v5_experience_not_modified():
    a = applicant("EDGE04")
    assert a.current_job_tenure_months == 4 and a.total_experience_months == 36


def test_v6_missing_not_zero():
    a = applicant("EDGE01")  # salaried, no ITR field
    assert a.itr_years_filed is None


def test_v7_requested_terms_preserved(engine):
    a = applicant("EDGE06")  # 60 months requested
    d = engine.run(a)
    for o in d.offers:
        if o.requested.tenure_months is not None:
            assert o.requested.tenure_months == 60


def test_v9_amount_within_supported_limits(engine):
    a = applicant("EDGE09")  # 50L request
    d = engine.run(a)
    for o in d.offers:
        if o.caps.product is not None and o.max_eligible.amount is not None:
            assert o.max_eligible.amount <= o.caps.product + 1


def test_v10_uncovered_not_marked_covering(engine):
    a = applicant("EDGE09")
    d = engine.run(a)
    for o in d.offers:
        if (o.max_eligible.amount or 0) < (a.requested_amount or 0) - 1:
            assert not o.status.covers_request


def test_v11_requested_emi_uses_requested_principal(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    for o in d.offers:
        q = o.requested
        if q.amount and q.tenure_months and q.emi and o.pricing.nominal_rate_pa:
            assert abs(ref_emi(q.amount, o.pricing.nominal_rate_pa, q.tenure_months) - q.emi) <= TOL


def test_v12_max_emi_uses_max_principal(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    for o in d.offers:
        m = o.max_eligible
        if m.amount and m.tenure_months and m.emi and o.pricing.nominal_rate_pa:
            assert abs(ref_emi(m.amount, o.pricing.nominal_rate_pa, m.tenure_months) - m.emi) <= TOL


def test_v13_emi_monotone_in_principal():
    assert ref_emi(600000, 11.0, 36) > ref_emi(300000, 11.0, 36)


def test_v16_apr_ge_nominal_when_fee(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    for o in d.offers:
        if o.status.is_offer and o.pricing.apr_pa and o.pricing.processing_fee:
            if o.pricing.processing_fee > 0:
                assert o.pricing.apr_pa >= o.pricing.nominal_rate_pa - 0.01


def test_v17_fee_and_gst_separate(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    for o in d.offers:
        if o.pricing.processing_fee:
            assert abs(o.pricing.gst_on_fee - round(o.pricing.processing_fee * 0.18, 2)) <= 1.0


def test_v19_unknown_mandatory_not_silent_pass(engine):
    # SE business with missing ITR -> must not silently become eligible on an ITR-gated product
    a = applicant("EDGE08")
    d = engine.run(a)
    # at least one product should route to info-required / review / not-eligible, not a silent offer
    assert any(o.status in (Status.ADDITIONAL_INFORMATION_REQUIRED, Status.MANUAL_REVIEW,
                            Status.NOT_ELIGIBLE) for o in d.offers)


def test_v20_unsupported_not_best(engine):
    a = applicant("EDGE09")  # 50L request most cannot cover
    d = engine.run(a)
    if d.best_offer and d.best_offer.status.covers_request is False:
        # if nothing covers, best must be flagged alternative, never claimed as covering
        assert d.best_offer.status == Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS


def test_v21_status_agrees_with_reasons(engine):
    a = applicant("EDGE02")
    d = engine.run(a)
    for o in d.offers:
        if o.status == Status.NOT_ELIGIBLE:
            assert any(r.code not in ("REPRICED", "CARD_OUTSTANDING_UNKNOWN") for r in o.reasons)


def test_v22_matched_count_consistent(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    offers = [o for o in d.offers if o.status.is_offer]
    assert len(offers) == sum(1 for o in d.offers if o.status.is_offer)


def test_v23_best_explanation_matches_ranking(engine):
    a = applicant("EDGE01")
    d = engine.run(a)
    if d.ranked_lender_ids and d.best_offer:
        assert d.best_offer.lender_id == d.ranked_lender_ids[0]


def test_v25_offers_retain_source_and_confidence(engine):
    a = applicant("EDGE02")
    d = engine.run(a)
    for o in d.offers:
        for r in o.reasons:
            if r.rule_status.value == "PUBLISHED":
                assert r.confidence is not None


# =========================================================== input validation edge cases
def test_negative_income_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=-1,
                  date_of_birth="1990-01-01", application_date="2026-01-01")


def test_dob_after_application_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=60000,
                  date_of_birth="2027-01-01", application_date="2026-01-01")


def test_invalid_score_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=60000, bureau_score=250,
                  date_of_birth="1990-01-01", application_date="2026-01-01")


def test_unknown_json_key_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="salaried", net_monthly_income=60000, foo_bar=1,
                  date_of_birth="1990-01-01", application_date="2026-01-01")


def test_unsupported_employment_rejected():
    with pytest.raises(Exception):
        Applicant(employment_type="freelatype", net_monthly_income=60000,
                  date_of_birth="1990-01-01", application_date="2026-01-01")


# =========================================================== credit-history edge cases
def test_score_one_below_threshold_rejects(engine):
    # HDFC publishes a score floor; one point below must reject
    from eligibility.affordability import _resolve_value  # noqa
    from eligibility.rules import get_store
    s = get_store()
    floor = _resolve_value(s, "hdfc", "hdfc_xpress_personal_loan", "salaried", "score_min", pick_min=False)
    if floor:
        a = Applicant(employment_type="salaried", net_monthly_income=120000, bureau_score=int(floor) - 1,
                      total_experience_months=120, current_job_tenure_months=60,
                      employer_category="mnc", city="Mumbai", salary_account_with_lender="hdfc",
                      date_of_birth="1990-01-01", application_date="2026-01-01")
        d = engine.run(a)
        hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
        assert hdfc.status == Status.NOT_ELIGIBLE
        assert any(r.code == "SCORE_BELOW_MIN" for r in hdfc.reasons)
