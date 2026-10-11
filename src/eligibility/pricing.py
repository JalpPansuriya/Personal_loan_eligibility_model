"""Pricing: nominal rate by score band, bureau repricing, processing fee + 18% GST, APR.

Rate selection (transparent, defensible):
  * Each lender publishes a rate_min_pa..rate_max_pa range. The nominal rate is placed
    within that range by score band: the best band gets rate_min, the worst gets rate_max,
    with a monotone ladder in between. New-to-credit is priced at the 700-749 level.
  * Women's concession: if the lender has any gender==female rate row (Union schemes), a
    small published-style concession is applied (never raises the rate, never gates).
  * Bureau repricing (agreed policy): NBFC soft flag -> +3pp and 50% amount haircut;
    fintech soft flag -> +5pp and 60% haircut.
  * Processing fee: percentage (on sanctioned amount) or flat, +18% GST on the fee.
  * APR: the IRR that equates the net disbursal (loan - fee - GST) to the EMI stream,
    annualised. Always >= nominal rate when a fee exists.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from typing import Optional

from scipy.optimize import brentq

from .finance import emi, monthly_rate
from .rules import RuleStore

GST = 0.18

# score band -> position in [0,1] from best (0=rate_min) to worst (1=rate_max)
BAND_POSITION = {">=800": 0.0, "750-799": 0.2, "700-749": 0.45, "650-699": 0.7, "<650": 1.0, "NTC": 0.45}

_DATE_RANGE = re.compile(r"between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})")
_VALID_TILL = re.compile(r"valid till\s+(\d{4}-\d{2}-\d{2})")


def _parse_window(text: str) -> tuple[Optional[_dt.date], Optional[_dt.date]]:
    """Extract an (effective, expiry) window from a fee-waiver condition string, if any."""
    t = (text or "").lower()
    m = _DATE_RANGE.search(t)
    if m:
        return _dt.date.fromisoformat(m.group(1)), _dt.date.fromisoformat(m.group(2))
    m = _VALID_TILL.search(t)
    if m:
        return None, _dt.date.fromisoformat(m.group(1))
    return None, None


def fee_waiver(store: RuleStore, lender: str, product: str, segment: str,
               application_date: Optional[_dt.date]) -> tuple[float, str]:
    """Return (waiver_fraction 0..1, note) for an UNCONDITIONAL, time-bound fee waiver that
    is in force on the application date. Conditional waivers (employer/BT eligibility) are
    NOT auto-applied; expired/future promotions are NOT applied (plan2 §7 effective dates)."""
    for ir in store.rules_for_variable(lender, product, segment, "processing_fee_waiver"):
        cond = ir.rule.condition or ""
        eff, exp = _parse_window(cond)
        if eff is None and exp is None:
            continue  # no dated window -> not a time-bound promo we can safely apply
        # only apply pure date-window waivers (no other applicant predicate we can't verify)
        if ir.cond.predicates:
            continue
        if application_date is None:
            continue
        if eff is not None and application_date < eff:
            continue  # future promo, not yet effective
        if exp is not None and application_date > exp:
            continue  # expired
        val = _num(ir.rule.value)
        frac = (val / 100.0) if val is not None else (1.0 if str(ir.rule.value).strip().lower() == "true" else 0.0)
        frac = max(0.0, min(1.0, frac))
        if frac > 0:
            win = f"{eff or '...'}..{exp or '...'}"
            return frac, f"time-bound processing-fee waiver applied ({win})"
    return 0.0, ""



def _num(v: str) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


@dataclass
class PriceResult:
    nominal_rate_pa: float
    apr_pa: float
    emi: float
    processing_fee: float          # incl GST
    tenure_months: int
    rate_source: str               # 'grid_range' | 'repriced'
    repriced: bool = False


def rate_bounds(store: RuleStore, lender: str, product: str, segment: str) -> tuple[float, float]:
    mins = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "rate_min_pa")
            if ir.rule.operator in (">=", "==") and _num(ir.rule.value) is not None and not ir.cond.predicates]
    maxs = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "rate_max_pa")
            if ir.rule.operator in ("<=", "==") and _num(ir.rule.value) is not None and not ir.cond.predicates]
    lo = min(mins) if mins else 12.0
    hi = max(maxs) if maxs else max(lo + 6.0, 18.0)
    if hi < lo:
        hi = lo
    return lo, hi


def has_women_concession(store: RuleStore, lender: str, product: str, segment: str) -> bool:
    return any("gender" in {p.field for p in ir.cond.predicates}
               for ir in store.scope(lender, product, segment)
               if ir.variable in ("rate_min_pa", "rate_grid", "segment_offered"))


def nominal_rate(store: RuleStore, lender: str, product: str, segment: str,
                 score_band: str, *, is_female: bool = False) -> tuple[float, str]:
    lo, hi = rate_bounds(store, lender, product, segment)
    pos = BAND_POSITION.get(score_band, 0.45)
    rate = lo + pos * (hi - lo)
    if is_female and has_women_concession(store, lender, product, segment):
        rate = max(lo, rate - 0.25)   # published women's concession on Union schemes
    return round(rate, 2), "grid_range"


def processing_fee(store: RuleStore, lender: str, product: str, segment: str,
                   amount: float) -> float:
    """Fee incl 18% GST. Uses pct (min/max clamp) or flat, whichever is published."""
    pct = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_pct")
           if _num(ir.rule.value) is not None and not ir.cond.predicates]
    flat = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_flat_inr")
            if _num(ir.rule.value) is not None and not ir.cond.predicates]
    fee = 0.0
    if pct:
        fee = (max(pct) / 100.0) * amount
        fmin = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_min_inr")
                if _num(ir.rule.value) is not None and not ir.cond.predicates]
        fmax = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_max_inr")
                if _num(ir.rule.value) is not None and not ir.cond.predicates]
        if fmin:
            fee = max(fee, max(fmin))
        if fmax:
            fee = min(fee, min(fmax))
    elif flat:
        fee = max(flat)
    return round(fee * (1 + GST), 2)


def fee_ex_gst(store: RuleStore, lender: str, product: str, segment: str, amount: float) -> float:
    """Processing fee BEFORE GST (so the breakdown can keep fee and GST separate)."""
    pct = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_pct")
           if _num(ir.rule.value) is not None and not ir.cond.predicates]
    flat = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_flat_inr")
            if _num(ir.rule.value) is not None and not ir.cond.predicates]
    fee = 0.0
    if pct:
        fee = (max(pct) / 100.0) * amount
        fmin = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_min_inr")
                if _num(ir.rule.value) is not None and not ir.cond.predicates]
        fmax = [_num(ir.rule.value) for ir in store.rules_for_variable(lender, product, segment, "processing_fee_max_inr")
                if _num(ir.rule.value) is not None and not ir.cond.predicates]
        if fmin:
            fee = max(fee, max(fmin))
        if fmax:
            fee = min(fee, min(fmax))
    elif flat:
        fee = max(flat)
    return round(fee, 2)


def rate_provenance(store: RuleStore, lender: str, product: str, segment: str):
    """Confidence, source URL and date of the lender's rate rows (for provenance display)."""
    rows = (store.rules_for_variable(lender, product, segment, "rate_min_pa")
            + store.rules_for_variable(lender, product, segment, "rate_max_pa"))
    pub = [ir for ir in rows if ir.rule.confidence.value in ("published", "published_conflict")]
    chosen = pub[0] if pub else (rows[0] if rows else None)
    if chosen is None:
        return (None, "", "")
    return (chosen.rule.confidence, chosen.rule.source_url, chosen.rule.accessed_date)


def apr(amount: float, nominal_pa: float, months: int, fee_incl_gst: float) -> float:
    """APR = annualised IRR equating net disbursal to the EMI stream."""
    e = emi(amount, nominal_pa, months)
    net = amount - fee_incl_gst
    if net <= 0:
        return nominal_pa
    # solve monthly i: net = e * (1 - (1+i)^-n)/i
    def f(i: float) -> float:
        if i <= 0:
            return e * months - net
        return e * (1 - (1 + i) ** -months) / i - net
    try:
        i = brentq(f, 1e-9, 1.0)
    except ValueError:
        return nominal_pa
    return round(i * 1200, 2)


def price(store: RuleStore, lender: str, product: str, segment: str, score_band: str,
          amount: float, months: int, *, is_female: bool = False,
          bureau_soft_flags: Optional[list[str]] = None) -> PriceResult:
    rate, src = nominal_rate(store, lender, product, segment, score_band, is_female=is_female)
    repriced = False
    flags = bureau_soft_flags or []
    if "reprice_nbfc" in flags:
        rate += 3.0
        repriced = True
        src = "repriced"
    elif "reprice_fintech" in flags:
        rate += 5.0
        repriced = True
        src = "repriced"
    fee = processing_fee(store, lender, product, segment, amount)
    e = emi(amount, rate, months)
    a = apr(amount, rate, months, fee)
    return PriceResult(nominal_rate_pa=round(rate, 2), apr_pa=a, emi=round(e, 2),
                       processing_fee=fee, tenure_months=months, rate_source=src, repriced=repriced)


def price_full(store: RuleStore, lender: str, product: str, segment: str, score_band: str,
               amount: float, months: int, *, is_female: bool = False,
               bureau_soft_flags: Optional[list[str]] = None,
               application_date: Optional[_dt.date] = None):
    """Full pricing breakdown (§4): rate, fee ex-GST, GST, net disbursement, totals, APR,
    with the rate's provenance and a range flag when the applicant rate is uncertain.
    Returns a PricingBreakdown plus the EMI for THIS amount/tenure."""
    from .schema import Confidence, PricingBreakdown  # local import to avoid cycle at module load

    rate, src = nominal_rate(store, lender, product, segment, score_band, is_female=is_female)
    flags = bureau_soft_flags or []
    if "reprice_nbfc" in flags:
        rate += 3.0
        src = "repriced"
    elif "reprice_fintech" in flags:
        rate += 5.0
        src = "repriced"
    rate = round(rate, 2)

    lo, hi = rate_bounds(store, lender, product, segment)
    conf, url, date = rate_provenance(store, lender, product, segment)

    fee = fee_ex_gst(store, lender, product, segment, amount)
    waiver_frac, waiver_note = fee_waiver(store, lender, product, segment, application_date)
    if waiver_frac > 0:
        fee = round(fee * (1 - waiver_frac), 2)
    gst = round(fee * GST, 2)
    e = round(emi(amount, rate, months), 2)
    total_repay = round(e * months, 2)
    net = round(amount - fee - gst, 2)
    total_cost = round(total_repay + fee + gst - amount, 2)
    a = apr(amount, rate, months, fee + gst)

    rate_estimated = conf not in (Confidence.PUBLISHED, Confidence.PUBLISHED_CONFLICT)
    notes = []
    if (hi - lo) > 0.01:
        notes.append("Rate placed within the lender's published band by score; the applicant's "
                     "actual rate may differ.")
    if rate_estimated:
        notes.append("Rate is estimated (not published); treat the APR as indicative.")
    if waiver_note:
        notes.append(waiver_note)

    return PricingBreakdown(
        nominal_rate_pa=rate,
        rate_is_range=(hi - lo) > 0.01,
        rate_min_pa=round(lo, 2), rate_max_pa=round(hi, 2),
        rate_source=src, rate_confidence=conf, rate_source_url=url, rate_accessed_date=date,
        processing_fee=fee, gst_on_fee=gst, other_charges=0.0,
        net_disbursement=net, total_repayment=total_repay, total_cost_of_credit=total_cost,
        apr_pa=a, apr_available=True,
        apr_note=" ".join(notes),
    ), e
