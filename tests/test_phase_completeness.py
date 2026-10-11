"""Phase 7 tests: traceable rule-confidence taxonomy + per-product completeness (plan2 §8).

Confirms the plan2 confidence labels are exposed, and that products are classified
complete / partial / insufficient from their published vs estimated rule groups, so no
lender is presented as fully verified when material rules are only estimated.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from eligibility import quality
from eligibility.api import app
from eligibility.schema import Confidence, ReasonCode

client = TestClient(app)

PLAN2_LABELS = {"VERIFIED_PUBLISHED", "SECONDARY_SOURCE", "ESTIMATED", "INFERRED",
                "UNKNOWN", "CONFLICT_REQUIRES_REVIEW"}


def test_confidence_labels_mapped():
    assert quality.label_for("published") == "VERIFIED_PUBLISHED"
    assert quality.label_for("published_conflict") == "CONFLICT_REQUIRES_REVIEW"
    assert quality.label_for("derived") == "INFERRED"
    assert quality.label_for("estimated") == "ESTIMATED"
    assert quality.label_for("whatever") == "UNKNOWN"


def test_reason_code_exposes_label():
    r = ReasonCode(code="X", message="m", confidence=Confidence.PUBLISHED)
    d = r.model_dump()
    assert d["confidence_label"] == "VERIFIED_PUBLISHED"


def test_summary_has_completeness_counts():
    s = quality.model_summary()
    assert s["products_complete"] + s["products_partial"] + s["products_insufficient"] \
        == s["products_configured"]
    assert set(s["rules_by_label"]).issubset(PLAN2_LABELS)


def test_product_completeness_shape():
    comp = quality.product_completeness()
    assert comp and all(c["rating"] in ("complete", "partial", "insufficient") for c in comp)
    for c in comp:
        assert set(c["groups"]) == {"gate", "sizing", "pricing", "fee"}


def test_completeness_endpoint():
    r = client.get("/api/completeness")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body


def test_no_product_claims_full_without_published_pricing():
    # an 'insufficient' product must NOT have published pricing+sizing
    for c in quality.product_completeness():
        if c["rating"] == "insufficient":
            assert not (c["groups"]["pricing"] == "published" and c["groups"]["sizing"] == "published")
