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
    return _resolve_value(store, lender, product, segment, "income_multiple_max", pick_min=True)


def product_max(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    return _resolve_value(store, lender, product, segment, "loan_max", pick_min=True)


def product_min(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    return _resolve_value(store, lender, product, segment, "loan_min", pick_min=False)


def take_home_floor(store: RuleStore, lender: str, product: str, segment: str) -> Optional[float]:
    return _resolve_value(store, lender, product, segment, "take_home_floor", pick_min=False)


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
    # For calibrated lenders the fitted calculator already embeds the FOIR model, so the
    # generic FOIR cap is skipped to avoid double-counting at a mismatched rate.
    fl = foir_limit(store, lender, product, segment)
    if fl is not None and "calculator" not in caps:
        emi_capacity = fl * d.assessed_income - d.total_obligations
        caps["foir"] = max(0.0, pv_annuity(emi_capacity, rate_pa, tenure_months))

    # take-home floor (Canara: keep max(25% net, 10k) after all EMIs; PNB fixed floors)
    thf = take_home_floor(store, lender, product, segment)
    if thf is not None:
        if lender == "canara":
            keep = max(0.25 * d.assessed_income, 10_000)
        else:
            keep = thf
        emi_capacity = d.assessed_income - d.total_obligations - keep
        caps["take_home"] = max(0.0, pv_annuity(emi_capacity, rate_pa, tenure_months))

    # income multiple
    mult = income_multiple(store, lender, product, segment)
    if mult is not None and "calculator" not in caps:
        caps["multiple"] = mult * d.assessed_income

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
    return SizingResult(max_loan=max_loan, binding_cap=binding, caps=caps, tenure_months=tenure_months)
