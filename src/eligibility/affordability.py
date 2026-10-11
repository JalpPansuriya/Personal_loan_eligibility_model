"""Loan sizing (affordability) for one applicant at one lender/product/segment.

The maximum loan is the smallest of all applicable caps:
  * FOIR capacity    : PV( foir_limit*income - obligations , rate, tenure )
  * take-home floor  : PV( income - obligations - floor , rate, tenure )  (Canara/PNB style)
  * income multiple  : multiple * income        (or Kotak's net-of-obligation multiple)
  * product maximum  : loan_max
Calibrated lenders (ICICI, Kotak) use their fitted calculator formula instead of the
generic FOIR/multiple, because that is what their real calculator does.

Returns a SizingResult recording the binding cap, so explanations can say *why* a loan
was limited. `rate` is supplied by the pricing layer; sizing takes it as input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import calibration
from .finance import floor_to, pv_annuity
from .preprocess import DerivedView
from .rules import IndexedRule, RuleStore
from .schema import Applicant

DEFAULT_ROUND = 1_000


def _num(v: str) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


@dataclass
class SizingResult:
    max_loan: float
    binding_cap: str              # foir | take_home | multiple | product | calculator
    caps: dict[str, float]        # every computed cap, for transparency
    tenure_months: int
    binding_is_estimated: bool = False  # True when the binding cap came from an estimated rule


def _resolve_value(store: RuleStore, lender: str, product: str, segment: str,
                   variable: str, *, pick_min: bool) -> Optional[float]:
    cands = [ir for ir in store.rules_for_variable(lender, product, segment, variable)
             if not ir.cond.predicates and _num(ir.rule.value) is not None]
    if not cands:
        return None
    vals = [_num(ir.rule.value) for ir in cands]
    return min(vals) if pick_min else max(vals)


def foir_limit(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    v = _resolve_value(store, lender, product, segment, "foir_max", pick_min=True)
    return v / 100.0 if v is not None else None


def income_multiple(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    # include variant-conditional multiples (e.g. Canara prime/delight both 25x); the
    # published multiple is the sizing rule even when the variant is unmodelled.
    cands = [ir for ir in store.rules_for_variable(lender, product, segment, "income_multiple_max")
             if _num(ir.rule.value) is not None]
    vals = [_num(ir.rule.value) for ir in cands]
    if vals:
        return min(vals)
    return _resolve_value(store, lender, product, segment, "income_multiple_max", pick_min=True)


def product_max(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    """Published product amount ceiling.

    loan_max rows are often conditioned on an unmodelled product variant (e.g. Canara
    Budget prime 50L / delight 40L). We do not know the variant, so we take the HIGHEST
    published variant ceiling as the hard cap: the loan can never exceed every variant's
    published maximum. This closes defect I (the vanishing cap when all loan_max rows were
    variant-conditional and therefore skipped by the unconditional-only resolver)."""
    cands = [ir for ir in store.rules_for_variable(lender, product, segment, "loan_max")
             if _num(ir.rule.value) is not None]
    vals = [_num(ir.rule.value) for ir in cands]
    return max(vals) if vals else None


def product_min(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    return _resolve_value(store, lender, product, segment, "loan_min", pick_min=False)


def take_home_floor(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    return _resolve_value(store, lender, product, segment, "take_home_floor", pick_min=False)


def selective_exception(store: RuleStore, lender: str, product: str, segment: str) -> tuple[bool, str]:
    """True if the lender's published cap text allows a higher amount only 'selectively'.
    Such exceptions are documented but NEVER applied automatically (plan2 §5, defect I)."""
    for ir in store.rules_for_variable(lender, product, segment, "loan_max"):
        blob = f"{ir.rule.quote} {ir.rule.notes}".lower()
        if "selective" in blob or "higher quantum" in blob or "higher amount" in blob:
            return True, "Lender may consider a higher amount selectively; not applied automatically."
    return False, ""


def _variable_is_estimated(store: RuleStore, lender: str, product: str, segment: str,
                           variable: str) -> bool:
    """True if every published-or-derived source for this sizing variable is absent, i.e.
    the only value available is estimated/inferred."""
    cands = [ir for ir in store.rules_for_variable(lender, product, segment, variable)
             if _num(ir.rule.value) is not None]
    if not cands:
        return False
    firm = {"published", "published_conflict", "derived"}
    return all(ir.rule.confidence.value not in firm for ir in cands)


def size_loan(store: RuleStore, app: Applicant, d: DerivedView, product: str, segment: str,
              rate_pa: float, tenure_months: int) -> SizingResult:
    lender = d.lender_id
    caps: dict[str, float] = {}

    # calibrated lenders: use the fitted calculator formula (income net of obligations)
    if lender == "kotak":
        caps["calculator"] = calibration.kotak_max_loan(d.assessed_income, d.total_obligations)
    elif lender == "icici" and segment in ("salaried", "all"):
        caps["calculator"] = calibration.icici_max_loan(d.assessed_income, d.total_obligations)

    # generic FOIR capacity.
    # generic FOIR capacity. When gross income was only ESTIMATED from net (BoB/PNB/Canara
    # with no supplied gross), applying a gross FOIR to the inflated figure double-counts, so
    # use net income for the FOIR capacity in that case (plan3 Case A).
    fl = foir_limit(store, lender, product, segment)
    if fl is not None and "calculator" not in caps:
        foir_base = d.net_monthly_income if d.gross_income_estimated else d.assessed_income
        emi_capacity = fl * foir_base - d.total_obligations
        caps["foir"] = max(0.0, pv_annuity(emi_capacity, rate_pa, tenure_months))

    # take-home floor (Canara: keep max(25% NET, 10k) after all EMIs; PNB fixed floors).
    # Canara's rule is on NET take-home pay, so the capacity base and keep-floor use NET
    # income, not the (possibly net->gross-estimated) assessed income (plan3 Case A).
    thf = take_home_floor(store, lender, product, segment)
    if thf is not None:
        if lender == "canara":
            base = d.net_monthly_income
            keep = max(0.25 * d.net_monthly_income, 10_000)
        else:
            base = d.assessed_income
            keep = thf
        emi_capacity = base - d.total_obligations - keep
        caps["take_home"] = max(0.0, pv_annuity(emi_capacity, rate_pa, tenure_months))

    # income multiple
    mult = income_multiple(store, lender, product, segment)
    if mult is not None and "calculator" not in caps:
        mult_base = d.net_monthly_income if d.gross_income_estimated else d.assessed_income
        caps["multiple"] = mult * mult_base

    # product ceiling
    pmax = product_max(store, lender, product, segment)
    if pmax is not None:
        caps["product"] = pmax

    if not caps:
        caps["product"] = 0.0

    binding = min(caps, key=lambda k: caps[k])
    max_loan = floor_to(caps[binding], DEFAULT_ROUND if lender not in ("kotak", "icici") else 10_000)
    # product ceiling still clips a calculator result
    if pmax is not None and max_loan > pmax:
        max_loan = pmax
        binding = "product"
    # flag an estimated binding cap (e.g. an estimated income multiple with no published cap)
    var_for_cap = {"multiple": "income_multiple_max", "product": "loan_max",
                   "foir": "foir_max", "take_home": "take_home_floor"}.get(binding)
    binding_est = bool(var_for_cap and _variable_is_estimated(store, lender, product, segment, var_for_cap))
    return SizingResult(max_loan=max_loan, binding_cap=binding, caps=caps,
                        tenure_months=tenure_months, binding_is_estimated=binding_est)
