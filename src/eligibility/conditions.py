"""Parse the free-text `condition` column into checkable predicates + metadata.

The rule table's `condition` field mixes two very different things:

  1. Real predicates that decide whether a rule applies to an applicant, e.g.
       gender==female
       city_tier in metro|urban
       salary_account==union
       loan_amount<=200000
       employer_category in govt|defence
       marital_status in single|widow|divorcee
       variant==prime
       channel==online

  2. Pricing/metadata annotations that are NOT applicant predicates, e.g.
       benchmark EBLR 8.25
       floating; RLLR 8.00 + CRP 4.65
       disclosure: APR offered Apr-Jun 2026
       w.e.f. 08.10.2026
       scheme==budget_individual     (an internal product scheme label, not an applicant field)

A condition string is a `;`-separated list of clauses. Each clause is parsed as a
predicate if it matches a known applicant/context field; otherwise it must match a
metadata pattern on the allowlist. If a clause matches NEITHER, parsing raises
UnknownClause so the Phase 1 gate fails loudly (we never silently drop a clause).

The parser returns a ParsedCondition with:
  * predicates : list[Predicate]  (ALL must hold for the rule to apply)
  * metadata    : list[str]        (annotations, kept for pricing/provenance)
  * scheme/variant/channel/tier/salary_account tags surfaced for the pricing layer
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# fields the engine can evaluate against an applicant + a per-lender context dict.
# value getters are resolved lazily in applies(): the context supplies them.
APPLICANT_FIELDS = {
    "gender", "marital_status", "city_tier", "city", "employer_category", "profession",
    "residence_type", "salary_account", "employer", "existing_axis_customer",
    "borrower_type", "loan_amount", "tenure_months", "disbursed_amount", "score",
    "channel", "variant", "scheme", "tier", "facility", "promo", "salary_package",
    "employer_undertaking", "category", "existing_borrower_with_satisfactory_record_months",
}

# clauses matching any of these (case-insensitive substring / regex) are metadata, not predicates.
METADATA_PATTERNS = [
    re.compile(p, re.I) for p in (
        r"^benchmark\b", r"\bEBLR\b", r"\bRLLR\b", r"\bMCLR\b", r"\bBRLLR\b", r"\bBSP\b",
        r"\bCRP\b", r"\bFRP\b", r"\bRLLR\+BSP\b", r"\bSP\b",
        r"^floating\b", r"^fixed\b", r"\bfloating\b.*grid", r"\bfixed\b.*grid",
        r"floating TL/OD", r"fixed TL/OD", r"term loan", r"facility==",
        r"^disclosure", r"^actual ", r"\bw\.e\.f\.", r"as on \d", r"quarter", r"Q1 FY",
        r"Apr-Jun|Apr'26|Sept 2026|FY ?2026", r"application between", r"valid till",
        r"festive|promo==|limited.?period|offer;",
        r"ROI PDF", r"product page grid", r"EMI calculator", r"calculator (slider|range)",
        r"supporting quote", r"part \d/\d", r"spread", r"benchmark=?\d",
        r"not on page", r"value not on page", r"contracted loans", r"new accounts",
        r"on principal outstanding", r"on overdue amount", r"part ?(pre)?payment",
        r"co-?applicants? not allowed", r"co-obligation", r"relationship with (any bank|BoB)",
        r"depends on income", r"linked to occupation", r"existing EMIs vs take-home",
        r"others$", r"others;", r"default tier", r"after existing and proposed",
        r"binding only when", r"whichever (lower|earlier)", r"remaining (period of )?service",
        r"in service", r"confirmed in service", r"when sanction based on salary credit",
        r"last 1 year salary", r"annual credits", r"GAI", r"guarantor", r"co-?obligant",
        r"third party", r"metro only", r"initially metro", r"each of last 2 years",
        r"x average gross", r"basis loan requirement", r"subject to", r"check_off",
        r"unless check_off", r"salary credit", r"undertaking", r"no reset",
        r"relationship with", r"with salary tie-up", r"without salary tie-up",
        r"with tie-up", r"salary tie-up", r"NTH", r"balance_transfer", r"emis?_paid",
        r"GST-incl", r"RLLR$", r"category A", r"category D", r"SB182", r"186",
        r"min_50pct_turnover", r"loan_type dependent",
        r"festive offer", r"application_date", r"metric==", r"^dpd\b", r"\bdpd\s*\d",
        r"SB/CA with PNB", r"annual credits in all accounts", r"previous FY",
    )
]

_OP_RE = re.compile(r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*(?P<op>==|!=|<=|>=|<|>|\bin\b)\s*(?P<val>.+)$")


class UnknownClause(ValueError):
    """A condition clause is neither a known predicate nor on the metadata allowlist."""


@dataclass(frozen=True)
class Predicate:
    field: str
    op: str                       # == != <= >= < > in
    values: tuple[str, ...]       # for 'in' this is the list; for scalar ops length 1

    def check(self, ctx: dict[str, Any]) -> Optional[bool]:
        """Evaluate against a context dict. Returns None when the field is absent/unknown
        (caller decides how to treat 'unknown'); True/False otherwise."""
        if self.field not in ctx or ctx[self.field] is None:
            return None
        actual = ctx[self.field]
        if self.op == "in":
            return _norm(actual) in {_norm(v) for v in self.values}
        if self.op in ("==", "!="):
            eq = _norm(actual) == _norm(self.values[0])
            return eq if self.op == "==" else not eq
        # numeric comparisons
        try:
            a = float(actual)
            b = float(self.values[0])
        except (TypeError, ValueError):
            return None
        return {"<=": a <= b, ">=": a >= b, "<": a < b, ">": a > b}[self.op]


@dataclass
class ParsedCondition:
    raw: str
    predicates: list[Predicate] = field(default_factory=list)
    metadata: list[str] = field(default_factory=list)

    def applies(self, ctx: dict[str, Any], *, unknown_is: bool = True) -> bool:
        """True iff every predicate holds. A predicate whose field is missing in ctx is
        treated as `unknown_is` (default True = 'do not block on unknown context')."""
        for p in self.predicates:
            res = p.check(ctx)
            if res is None:
                if not unknown_is:
                    return False
                continue
            if not res:
                return False
        return True


def _norm(v: Any) -> str:
    return str(v).strip().lower()


def _is_metadata(clause: str) -> bool:
    return any(p.search(clause) for p in METADATA_PATTERNS)


def parse_condition(raw: str) -> ParsedCondition:
    """Parse one condition string. Raises UnknownClause if a clause can't be classified."""
    pc = ParsedCondition(raw=raw)
    text = (raw or "").strip()
    if not text:
        return pc
    for clause in (c.strip() for c in text.split(";")):
        if not clause:
            continue
        # try the first segment of 'a & b' compound predicate forms too
        handled = False
        for part in re.split(r"\s*&\s*", clause):
            part = part.strip()
            if not part:
                continue
            m = _OP_RE.match(part)
            if m and m.group("field") in APPLICANT_FIELDS:
                field_name, op, val = m.group("field"), m.group("op"), m.group("val").strip()
                values = tuple(v.strip() for v in val.split("|")) if op == "in" else (val,)
                pc.predicates.append(Predicate(field_name, op, values))
                handled = True
            elif _is_metadata(part):
                pc.metadata.append(part)
                handled = True
            else:
                # a full-clause metadata match (e.g. the clause has ';'-less annotations)
                if _is_metadata(clause):
                    pc.metadata.append(clause)
                    handled = True
                    break
                raise UnknownClause(f"cannot classify clause {part!r} in condition {raw!r}")
        if not handled:
            raise UnknownClause(f"cannot classify condition {raw!r}")
    return pc
