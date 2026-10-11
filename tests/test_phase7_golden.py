"""Phase 7 gate: end-to-end golden profiles + population sanity.

* each P01-P16 engine output matches its reviewed golden JSON exactly
* the run is deterministic
* a synthetic population runs with no crashes and is reproducible with a fixed seed
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eligibility.engine import Engine
from eligibility.schema import Applicant
from eligibility.simulate import population, run_population

ROOT = Path(__file__).resolve().parent
PROF = ROOT / "profiles"
GOLD = ROOT / "golden"

PROFILE_IDS = [f"P{i:02d}" for i in range(1, 17)]


@pytest.fixture(scope="module")
def engine():
    return Engine()


def _summ(app, engine):
    d = engine.run(app)
    return {
        "eligible": d.eligible,
        "offer_count": sum(1 for o in d.offers if o.status.is_offer),
        "best": None if not d.best_offer else {
            "lender_id": d.best_offer.lender_id, "status": d.best_offer.status.value,
            "max_eligible": d.best_offer.max_eligible.amount, "apr_pa": d.best_offer.pricing.apr_pa},
        "offers": {o.lender_id: {"status": o.status.value, "max_eligible": o.max_eligible.amount,
                                 "apr_pa": o.pricing.apr_pa} for o in d.offers},
    }


@pytest.mark.parametrize("pid", PROFILE_IDS)
def test_golden_profile_matches(engine, pid):
    rec = json.loads((PROF / f"{pid}.json").read_text(encoding="utf-8"))
    rec.pop("profile_id", None)
    rec.pop("description", None)
    got = _summ(Applicant(**rec), engine)
    want = json.loads((GOLD / f"{pid}.json").read_text(encoding="utf-8"))
    assert got == want, f"{pid} diverged from golden baseline"


def test_all_profiles_present():
    assert sorted(p.stem for p in PROF.glob("P*.json")) == PROFILE_IDS
    assert sorted(p.stem for p in GOLD.glob("P*.json")) == PROFILE_IDS


def test_no_zero_amount_offers(engine):
    # a passing offer must have a positive max eligible amount (regression guard)
    for pid in PROFILE_IDS:
        rec = json.loads((PROF / f"{pid}.json").read_text(encoding="utf-8"))
        rec.pop("profile_id", None); rec.pop("description", None)
        d = engine.run(Applicant(**rec))
        for o in d.offers:
            if o.status.is_offer:
                assert (o.max_eligible.amount or 0) >= 1000, f"{pid}: {o.lender_id} offered {o.max_eligible.amount}"


def test_population_runs_and_is_reproducible(engine):
    a = population(300, seed=7)
    b = population(300, seed=7)
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    stats = run_population(a, engine)
    assert stats.n == len(a)
    assert 0.0 <= stats.eligible_rate <= 1.0
    assert stats.avg_offers >= 0


def test_population_no_crash_varied_profiles(engine):
    # includes NTC, writeoffs, self-employed, low income - must not raise
    apps = population(500, seed=99)
    stats = run_population(apps, engine)
    assert stats.n > 0
