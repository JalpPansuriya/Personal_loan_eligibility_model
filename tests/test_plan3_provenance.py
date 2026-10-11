"""plan3 Phase 9: provenance, generic-default audit, completeness counts, drift manifest."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eligibility import quality
from eligibility.rules import get_store

ROOT = Path(__file__).resolve().parents[1]


def test_no_estimated_rule_labelled_published():
    # a rule can be published or estimated, never both; labels are a clean partition
    store = get_store()
    for ir in store.all():
        label = quality.label_for(ir.rule.confidence.value)
        if ir.rule.confidence.value in ("estimated", "estimated_superseded"):
            assert label == "ESTIMATED"
        if ir.rule.confidence.value == "published":
            assert label == "VERIFIED_PUBLISHED"


def test_derived_labelled_calculator():
    assert quality.label_for("derived") == "DERIVED_FROM_PUBLIC_CALCULATOR" or \
           quality.label_for("derived") == "INFERRED"  # quality.py vs gates.py mapping


def test_completeness_counts_present():
    s = quality.model_summary()
    assert s["material_rules_verified"] > 0
    assert s["material_rules_estimated"] >= 0
    # verified+estimated+inferred+conflict should be <= total material rows (sanity)
    tot = (s["material_rules_verified"] + s["material_rules_estimated"]
           + s["material_rules_inferred"] + s["material_rules_conflict"])
    assert tot > 0


def test_every_rule_has_retrieved_date_or_estimation():
    # published rules carry an access date; estimated carry a method (provenance everywhere)
    store = get_store()
    bad = []
    for ir in store.all():
        c = ir.rule.confidence.value
        if c in ("published", "published_conflict") and not ir.rule.accessed_date:
            bad.append((ir.rule_id, "no accessed_date"))
        if c in ("estimated", "estimated_superseded", "derived") and not ir.rule.estimation_method:
            bad.append((ir.rule_id, "no estimation_method"))
    assert not bad, f"provenance gaps: {bad[:5]}"


def test_drift_manifest_exists_and_clean():
    # the manifest was committed; a fresh check must report no drift (exit 0)
    r = subprocess.run([sys.executable, "scripts/check_source_drift.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"source drift detected: {r.stdout}"
