"""Phase 1 gate: rule store + condition parser.

* every one of the real conditions parses (0 UnknownClause)
* parsed predicates evaluate correctly for true / false / missing-field
* metadata-only conditions carry no predicate
* the rule store indexes all 20 lenders and fixes per-lender counts (snapshot) so a
  future edit cannot silently drop rows
"""
from __future__ import annotations

import csv

import pytest

from eligibility import paths
from eligibility.conditions import Predicate, UnknownClause, parse_condition
from eligibility.rules import RuleStore, get_store
from eligibility.schema import LENDERS


def _all_conditions() -> set[str]:
    with paths.RULES_LONG.open(encoding="utf-8-sig", newline="") as fh:
        return {r["condition"].strip() for r in csv.DictReader(fh)}


# --------------------------------------------------------------------------- parser coverage
def test_every_condition_parses():
    bad = []
    for c in _all_conditions():
        try:
            parse_condition(c)
        except UnknownClause as exc:
            bad.append((c, str(exc)))
    assert not bad, f"{len(bad)} conditions failed to parse; first: {bad[:5]}"


def test_empty_condition_is_empty():
    pc = parse_condition("")
    assert pc.predicates == [] and pc.metadata == []


# --------------------------------------------------------------------------- predicate logic
def test_eq_predicate_true_false_missing():
    pc = parse_condition("gender==female")
    assert len(pc.predicates) == 1
    p = pc.predicates[0]
    assert p.check({"gender": "female"}) is True
    assert p.check({"gender": "male"}) is False
    assert p.check({}) is None            # missing field -> unknown


def test_in_predicate():
    pc = parse_condition("employer_category in govt|defence")
    p = pc.predicates[0]
    assert p.check({"employer_category": "govt"}) is True
    assert p.check({"employer_category": "defence"}) is True
    assert p.check({"employer_category": "private"}) is False


def test_numeric_predicate():
    pc = parse_condition("loan_amount<=200000")
    p = pc.predicates[0]
    assert p.check({"loan_amount": 150000}) is True
    assert p.check({"loan_amount": 200000}) is True
    assert p.check({"loan_amount": 250000}) is False


def test_not_equal_predicate():
    pc = parse_condition("salary_account!=union")
    p = pc.predicates[0]
    assert p.check({"salary_account": "hdfc"}) is True
    assert p.check({"salary_account": "union"}) is False


def test_compound_predicate_with_ampersand():
    pc = parse_condition("salary_account==union & employer_undertaking==yes; benchmark EBLR 8.25")
    # two predicates + one metadata note
    assert len(pc.predicates) == 2
    assert any("benchmark" in m.lower() for m in pc.metadata)
    ctx = {"salary_account": "union", "employer_undertaking": "yes"}
    assert pc.applies(ctx) is True
    assert pc.applies({"salary_account": "union", "employer_undertaking": "no"}) is False


def test_metadata_only_condition_has_no_predicate():
    pc = parse_condition("benchmark EBLR 8.25")
    assert pc.predicates == []
    assert pc.metadata


def test_applies_unknown_is_true_by_default():
    pc = parse_condition("city_tier in metro|urban")
    assert pc.applies({}) is True                 # unknown context -> rule still applies
    assert pc.applies({}, unknown_is=False) is False
    assert pc.applies({"city_tier": "metro"}) is True
    assert pc.applies({"city_tier": "rural"}) is False


def test_predicate_case_insensitive():
    p = Predicate("gender", "==", ("female",))
    assert p.check({"gender": "FEMALE"}) is True


# --------------------------------------------------------------------------- rule store
def test_store_loads_all_lenders():
    s = get_store()
    assert set(s.counts_by_lender()) == set(LENDERS)


def test_store_scope_includes_all_segment_rows():
    s = get_store()
    # idfc has many segment='all' rows for firstmoney
    scoped = s.scope("idfc", "idfc_firstmoney", "salaried")
    variables = {ir.variable for ir in scoped}
    # age_min is published as segment='all' - must surface under the salaried scope
    assert "age_min" in variables


# snapshot of per-lender rule counts (from the current rule table). If an edit changes
# these, this test fails and forces a deliberate re-baseline.
EXPECTED_LENDER_COUNTS = {
    "abcl": 70, "axis": 43, "bajaj": 45, "bob": 107, "canara": 71, "hdfc": 40, "icici": 56,
    "idfc": 47, "indusind": 42, "kotak": 39, "kreditbee": 53, "lnt": 77, "moneyview": 37,
    "navi": 25, "pnb": 89, "poonawalla": 101, "sbi": 48, "tata": 49, "union": 197, "yes": 23,
}


def test_store_counts_match_snapshot():
    s = get_store()
    got = s.counts_by_lender()
    assert got == EXPECTED_LENDER_COUNTS, (
        "per-lender rule counts changed; if intentional, update EXPECTED_LENDER_COUNTS. "
        f"diff: { {k: (EXPECTED_LENDER_COUNTS.get(k), got.get(k)) for k in set(EXPECTED_LENDER_COUNTS)|set(got) if EXPECTED_LENDER_COUNTS.get(k)!=got.get(k)} }"
    )


def test_store_total_is_1259():
    s = get_store()
    assert len(s.all()) == 1259
