"""Rule store: load data/lender_rules_long.csv, index it, pre-parse conditions.

This is the single source of truth the engine queries. It never mutates the CSV.
Conditions are parsed once at load time; an unparseable condition raises immediately
(the Phase 1 gate relies on this).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

from . import paths
from .conditions import ParsedCondition, parse_condition
from .schema import LENDER_TYPE, LENDERS, Rule

# effect/variable rows that never gate or size - kept for provenance only
INFO_ONLY_VARIABLES = {"foreclosure", "penal_charge", "bounce_charge", "lending_entity"}


@dataclass
class IndexedRule:
    rule: Rule
    cond: ParsedCondition

    # convenience passthroughs
    @property
    def rule_id(self) -> str:
        return self.rule.rule_id

    @property
    def variable(self) -> str:
        return self.rule.variable

    @property
    def effect(self) -> str:
        return self.rule.effect


class RuleStore:
    def __init__(self, rows: Iterable[dict]):
        self._all: list[IndexedRule] = []
        # (lender, product, segment) -> list[IndexedRule]
        self._by_scope: dict[tuple[str, str, str], list[IndexedRule]] = defaultdict(list)
        # lender -> set of products
        self._products: dict[str, set[str]] = defaultdict(set)
        # lender -> set of segments offered (from any product)
        self._segments: dict[str, set[str]] = defaultdict(set)

        for raw in rows:
            rule = Rule(**raw)
            cond = parse_condition(rule.condition)
            ir = IndexedRule(rule=rule, cond=cond)
            self._all.append(ir)
            self._by_scope[(rule.lender_id, rule.product, rule.segment)].append(ir)
            self._products[rule.lender_id].add(rule.product)
            self._segments[rule.lender_id].add(rule.segment)

    # ---------------------------------------------------------------- factory
    @classmethod
    def load(cls, path=None) -> "RuleStore":
        path = path or paths.RULES_LONG
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return cls(list(csv.DictReader(fh)))

    # ---------------------------------------------------------------- queries
    def all(self) -> list[IndexedRule]:
        return list(self._all)

    def lenders(self) -> tuple[str, ...]:
        return LENDERS

    def products(self, lender_id: str) -> list[str]:
        return sorted(self._products.get(lender_id, set()))

    def lender_type(self, lender_id: str) -> str:
        return LENDER_TYPE[lender_id]

    def scope(self, lender_id: str, product: str, segment: str) -> list[IndexedRule]:
        """Rules for an exact lender/product/segment, plus product rows marked segment='all'."""
        out = list(self._by_scope.get((lender_id, product, segment), []))
        if segment != "all":
            out += self._by_scope.get((lender_id, product, "all"), [])
        return out

    def products_for_segment(self, lender_id: str, segment: str) -> list[str]:
        """Products this lender offers that have at least one rule row for this segment
        (or an 'all' row)."""
        out = set()
        for (lid, product, seg) in self._by_scope:
            if lid == lender_id and seg in (segment, "all"):
                out.add(product)
        return sorted(out)

    def rules_for_variable(self, lender_id: str, product: str, segment: str,
                           variable: str) -> list[IndexedRule]:
        return [ir for ir in self.scope(lender_id, product, segment) if ir.variable == variable]

    def counts_by_confidence(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for ir in self._all:
            c[ir.rule.confidence.value] += 1
        return dict(c)

    def counts_by_lender(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for ir in self._all:
            c[ir.rule.lender_id] += 1
        return dict(c)


@lru_cache(maxsize=1)
def get_store() -> RuleStore:
    """Cached singleton for engine use."""
    return RuleStore.load()
