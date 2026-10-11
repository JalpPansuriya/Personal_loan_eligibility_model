"""Backend API gate: FastAPI endpoints over the engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient   # noqa: E402

from eligibility.api import app             # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROF = ROOT / "tests" / "profiles"
client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_meta_shape():
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = r.json()
    assert len(m["lenders"]) == 20
    assert "salaried" in m["employment_types"]
    assert "female" in m["genders"]
    assert m["tenures"]


def test_profiles_list():
    r = client.get("/api/profiles")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 16
    assert any(p["profile_id"] == "P01" for p in data)


def test_summary_endpoint():
    r = client.get("/api/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["lenders_configured"] == 20
    assert "products_with_published_rules" in s


def test_evaluate_offer_shape_separates_requested_and_max():
    rec = {"employment_type": "salaried", "net_monthly_income": 200000,
           "requested_amount": 500000, "requested_tenure_months": 36,
           "bureau_score": 800, "employer_category": "private_ltd", "city": "Mumbai",
           "date_of_birth": "1990-01-01", "application_date": "2026-01-01"}
    r = client.post("/api/evaluate", json=rec)
    assert r.status_code == 200, r.text
    best = r.json()["best_offer"]
    assert best["requested"]["amount"] == 500000
    assert best["max_eligible"]["amount"] > 1000000
    assert best["requested"]["emi"] != best["max_eligible"]["emi"]
    assert "pricing" in best and "apr_pa" in best["pricing"]


def test_evaluate_prime_profile():
    rec = json.loads((PROF / "P01.json").read_text(encoding="utf-8"))
    r = client.post("/api/evaluate", json=rec)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["eligible"] is True
    assert len(d["offers"]) == 20
    assert d["best_offer"]["lender_id"]
    # every offer has a fixes array (empty for approved)
    assert all("fixes" in o for o in d["offers"])


def test_evaluate_rejected_has_fixes():
    rec = json.loads((PROF / "P04.json").read_text(encoding="utf-8"))
    r = client.post("/api/evaluate", json=rec)
    d = r.json()
    rejected = [o for o in d["offers"] if o["status"] == "NOT_ELIGIBLE"]
    assert rejected
    # every non-eligible offer carries a fixes list (possibly empty)
    assert all(isinstance(o["fixes"], list) for o in rejected)


def test_evaluate_minimal_body():
    body = {"employment_type": "salaried", "net_monthly_income": 60000,
            "date_of_birth": "1990-01-01", "application_date": "2026-01-01"}
    r = client.post("/api/evaluate", json=body)
    assert r.status_code == 200
    assert len(r.json()["offers"]) == 20


def test_evaluate_invalid_returns_422():
    body = {"employment_type": "salaried", "net_monthly_income": 60000,
            "bureau_score": 0, "date_of_birth": "1990-01-01"}
    r = client.post("/api/evaluate", json=body)
    assert r.status_code == 422


def test_evaluate_ignores_profile_metadata():
    rec = json.loads((PROF / "P14.json").read_text(encoding="utf-8"))
    assert "profile_id" in rec
    r = client.post("/api/evaluate", json=rec)
    assert r.status_code == 200
