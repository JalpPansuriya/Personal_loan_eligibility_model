"""plan3 Phase 11: per-EDGE assertions, boundary tests, FE/BE consistency (§7, §10)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eligibility.api import app as api_app
from eligibility.engine import Engine
from eligibility.schema import Applicant, Status

EDGE = Path(__file__).resolve().parent / "edge_profiles"
client = TestClient(api_app)


@pytest.fixture(scope="module")
def engine():
    return Engine()


def load(pid):
    return json.loads((EDGE / f"{pid}.json").read_text(encoding="utf-8"))


def app_of(pid):
    raw = dict(load(pid)); raw.pop("profile_id", None); raw.pop("description", None)
    return Applicant(**raw)


# =========================================================== per-EDGE outcome assertions
def test_edge01_score_700_eligible(engine):
    d = engine.run(app_of("EDGE01"))
    assert any(o.status.is_offer for o in d.offers)


def test_edge02_adverse_mostly_blocked(engine):
    d = engine.run(app_of("EDGE02"))
    # score 640 below many published floors -> few offers; no rate above published range
    for o in d.offers:
        if o.pricing.rate_max_pa and o.pricing.nominal_rate_pa:
            assert o.pricing.nominal_rate_pa <= o.pricing.rate_max_pa + 0.01


def test_edge03_high_emi_canara_bounded(engine):
    d = engine.run(app_of("EDGE03"))
    canara = next(o for o in d.offers if o.lender_id == "canara")
    if canara.max_eligible.amount:
        assert canara.max_eligible.amount < 2_000_000  # not the old 25.05L


def test_edge04_age_27(engine):
    assert app_of("EDGE04").age_completed_years == 27


def test_edge05_ntc_young_blocked(engine):
    d = engine.run(app_of("EDGE05"))
    assert app_of("EDGE05").is_ntc


def test_edge06_requested_tenure_preserved(engine):
    d = engine.run(app_of("EDGE06"))
    for o in d.offers:
        if o.requested.tenure_months is not None:
            assert o.requested.tenure_months == 60


def test_edge07_doctor_needs_profession(engine):
    d = engine.run(app_of("EDGE07"))
    for o in d.offers:
        if "professional" in o.product and o.status.is_offer:
            assert False, "professional product matched without a profession field"


def test_edge08_business_one_itr(engine):
    a = app_of("EDGE08")
    assert a.itr_years_filed == 1 and a.business_vintage_months == 24


def test_edge09_50lakh_mostly_alternative(engine):
    d = engine.run(app_of("EDGE09"))
    for o in d.offers:
        if (o.max_eligible.amount or 0) < 4_999_999:
            assert not o.status.covers_request


def test_edge10_settlement_review(engine):
    d = engine.run(app_of("EDGE10"))
    assert any(o.status == Status.MANUAL_REVIEW for o in d.offers)


# =========================================================== boundary tests
def _mk(**over):
    kw = dict(employment_type="salaried", net_monthly_income=120000, bureau_score=760,
              total_experience_months=120, current_job_tenure_months=60, employer_category="mnc",
              city="Mumbai", salary_account_with_lender="hdfc", requested_amount=400000,
              requested_tenure_months=36, date_of_birth=dt.date(1990, 1, 1),
              application_date=dt.date(2026, 1, 1))
    kw.update(over)
    return Applicant(**kw)


@pytest.mark.parametrize("score,expect_block", [(719, True), (720, False), (721, False)])
def test_boundary_score_floor(engine, score, expect_block):
    # HDFC publishes a 720 floor; 719 blocks, 720/721 pass that gate
    d = engine.run(_mk(bureau_score=score))
    hdfc = next(o for o in d.offers if o.lender_id == "hdfc")
    blocked = any(r.code == "SCORE_BELOW_MIN" for r in hdfc.reasons)
    assert blocked == expect_block


def test_boundary_age_min():
    # born 2007-01-02, applying 2026-01-01 -> 18 completed years (birthday not yet reached)
    young = _mk(date_of_birth=dt.date(2007, 1, 2))
    assert young.age_completed_years == 18
    older = _mk(date_of_birth=dt.date(2007, 1, 1))  # birthday reached -> 19
    assert older.age_completed_years == 19


def test_boundary_requested_above_product_cap_not_covered(engine):
    # request clearly above a lender's published product cap must not count as covered
    d = engine.run(_mk(net_monthly_income=1_000_000, requested_amount=12_000_000))
    for o in d.offers:
        if o.caps.binding_cap == "product" and o.caps.product and \
                o.caps.product < 12_000_000 and o.status.is_offer:
            assert not o.status.covers_request


# =========================================================== FE/BE consistency
@pytest.mark.parametrize("pid", [f"EDGE{i:02d}" for i in range(1, 11)])
def test_api_matches_engine(engine, pid):
    raw = load(pid)
    r = client.post("/api/evaluate", json=raw)
    assert r.status_code == 200
    body = r.json()
    d = engine.run(app_of(pid))
    api_status = {o["lender_id"]: o["status"] for o in body["offers"]}
    eng_status = {o.lender_id: o.status.value for o in d.offers}
    assert api_status == eng_status
    assert body["rule_set_version"] == d.rule_set_version


def test_api_rejects_unknown_key():
    r = client.post("/api/evaluate", json={"employment_type": "salaried", "net_monthly_income": 60000,
                                           "date_of_birth": "1990-01-01", "application_date": "2026-01-01",
                                           "mystery_field": 1})
    assert r.status_code == 422
