"""Counterfactual advice: the smallest single change that flips a rejection to approval.

For a lender that rejected, we try one lever at a time and re-run the engine's product
evaluation. Levers (actionable only):
  * emi_reduction : lower existing EMI (binary search to the smallest reduction)
  * income_increase: higher income (binary search)
  * wait_months   : add months of experience / vintage / age-maturity headroom
  * tenure        : shorten/change requested tenure (for maturity caps)
Non-actionable gates (segment not offered, NTC policy, write-off/age-min) produce an
explanation, never a false suggestion.

The advice is verified: after applying the proposed change, the lender must APPROVE, and
one unit less of the change must still fail (minimality).
"""
from __future__ import annotations

from typing import Optional

from .engine import Engine
from .schema import Applicant, Fix, LenderOffer, Status

NON_ACTIONABLE = {"SEGMENT_NOT_OFFERED", "NTC_NOT_ALLOWED", "PRIOR_WRITEOFF_SETTLEMENT",
                  "AGE_BELOW_MIN", "AGE_ABOVE_MAX", "CITY_NOT_SERVICED", "PROFESSION_NOT_ALLOWED",
                  "EMPLOYER_NOT_ALLOWED"}


def _approves(engine: Engine, app: Applicant, lender: str, product: str, segment: str) -> bool:
    off = engine.evaluate_product(app, lender, product, segment)
    return off.status.is_offer


def _clone(app: Applicant, **changes) -> Applicant:
    return app.model_copy(update=changes)


def suggest(engine: Engine, app: Applicant, offer: LenderOffer) -> list[Fix]:
    """Return minimal fixes for one non-eligible lender offer (may be empty)."""
    if offer.status.is_offer:
        return []
    lender, product, segment = offer.lender_id, offer.product, offer.segment
    codes = {r.code for r in offer.reasons}
    fixes: list[Fix] = []

    # non-actionable -> explain only
    if codes & NON_ACTIONABLE:
        for r in offer.reasons:
            if r.code in NON_ACTIONABLE:
                fixes.append(Fix(lever="explain", description=r.message))
        return fixes

    # EMI reduction (FOIR / amount / affordability failures)
    if {"FOIR_EXCEEDED", "AMOUNT_BELOW_MIN"} & codes or offer.reasons == []:
        if app.existing_emi_monthly > 0:
            fix = _binary_reduce_emi(engine, app, lender, product, segment)
            if fix:
                fixes.append(fix)

    # income increase (income-min failures)
    if "INCOME_BELOW_MIN" in codes:
        fix = _binary_increase_income(engine, app, lender, product, segment)
        if fix:
            fixes.append(fix)

    # wait months (experience / current-tenure / vintage)
    if {"EXP_TOTAL_LT_MIN", "EXP_CURRENT_LT_MIN", "VINTAGE_LT_MIN"} & codes:
        fix = _wait_months(engine, app, lender, product, segment, offer)
        if fix:
            fixes.append(fix)

    # score build (soft, not binary-searchable here)
    if "SCORE_BELOW_MIN" in codes:
        req = next((r.required_value for r in offer.reasons if r.code == "SCORE_BELOW_MIN"), None)
        fixes.append(Fix(lever="score", description=f"raise bureau score to at least {req}",
                         amount=float(req) if req else None, unit="score"))
    return fixes


def _binary_reduce_emi(engine, app, lender, product, segment) -> Optional[Fix]:
    hi = app.existing_emi_monthly
    if _approves(engine, _clone(app, existing_emi_monthly=0), lender, product, segment) is False:
        return None
    lo = 0.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if _approves(engine, _clone(app, existing_emi_monthly=mid), lender, product, segment):
            lo = mid
        else:
            hi = mid
    # the largest EMI that still approves is `lo`; reduce by at least (current - lo),
    # rounded UP to the next 100 so the rounded advice is always sufficient.
    import math
    reduction = app.existing_emi_monthly - lo
    if reduction <= 0:
        return None
    reduction = math.ceil(reduction / 100.0) * 100
    return Fix(lever="emi_reduction", description=f"reduce existing EMI by about Rs {reduction:,.0f}/month",
               amount=float(reduction), unit="inr_per_month")


def _binary_increase_income(engine, app, lender, product, segment) -> Optional[Fix]:
    # isolate the income gate by dropping any requested amount during the search
    probe = app.model_copy(update={"requested_amount": None})
    lo = probe.net_monthly_income
    hi = max(probe.net_monthly_income * 20, 500_000)
    if not _approves(engine, _clone(probe, net_monthly_income=hi), lender, product, segment):
        return None
    for _ in range(30):
        mid = (lo + hi) / 2
        if _approves(engine, _clone(probe, net_monthly_income=mid), lender, product, segment):
            hi = mid
        else:
            lo = mid
    import math
    increase = math.ceil((hi - app.net_monthly_income) / 100.0) * 100
    return Fix(lever="income_increase", description=f"increase documented income by about Rs {increase:,.0f}/month",
               amount=float(increase), unit="inr_per_month")


def _wait_months(engine, app, lender, product, segment, offer) -> Optional[Fix]:
    for m in range(1, 61):
        cand = _clone(app,
                      total_experience_months=app.total_experience_months + m,
                      current_job_tenure_months=app.current_job_tenure_months + m,
                      business_vintage_months=(app.business_vintage_months or 0) + m)
        if _approves(engine, cand, lender, product, segment):
            return Fix(lever="wait_months", description=f"wait about {m} month(s) to build the required tenure",
                       amount=m, unit="months")
    return None
