"""Preprocessing: derive F23-F34 (the system/lender-specific features).

Raw applicant features (F01-F22, F35) live on the Applicant model. The derived features
depend on the lender's reading of income, its FOIR limit, and its maturity cap, so they
are computed per (applicant, lender, product, segment) as a DerivedView.

Nothing here gates or sizes; it only computes the numbers the gate/affordability layers
read. NULL discipline is preserved (bureau fields stay None).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import lookups
from .schema import Applicant, EmploymentType

CARD_LOAD = 0.05            # monthly obligation = 5% of card outstanding (estimated, documented)
GROSS_FROM_NET = 1 / 0.75   # net -> gross approximation for gross-FOIR lenders (estimated)

# lenders that assess income on a GROSS basis (from income_mode==gross rows in the rule table)
GROSS_INCOME_LENDERS = {"bob", "pnb", "canara"}


def score_band(score: Optional[int]) -> str:
    """F31: >=800 | 750-799 | 700-749 | 650-699 | <650 | NTC."""
    if score is None:
        return "NTC"
    if score >= 800:
        return ">=800"
    if score >= 750:
        return "750-799"
    if score >= 700:
        return "700-749"
    if score >= 650:
        return "650-699"
    return "<650"


@dataclass
class DerivedView:
    """Derived features for one applicant as read by one lender/product/segment."""
    lender_id: str
    product: str
    segment: str

    age_at_application: float          # F23
    assessed_income: float             # F26 (net or gross per lender)
    income_mode: str                   # 'net' | 'gross'
    total_obligations: float           # F27
    current_foir: float                # F28
    score_band: str                    # F31
    bureau_clean: bool                 # F32
    itr_income_growth: Optional[float] # F33
    city_tier: Optional[int]
    city_tier_band: str

    def age_at_maturity(self, tenure_months: int) -> float:   # F24
        return self.age_at_application + tenure_months / 12.0


def obligations(app: Applicant) -> float:
    """F27: existing EMI + the card's monthly obligation.

    The card obligation is the supplied card_monthly_payment; when the balance is positive
    but the payment is unknown it is NOT imputed (0 here) and the engine flags
    CARD_PAYMENT_UNKNOWN so the max is marked indicative (plan3 Case D)."""
    return app.existing_emi_monthly + app.card_obligation


def assessed_income(app: Applicant, lender_id: str) -> tuple[float, str]:
    """F26: income as the lender reads it.

    * Salaried gross-FOIR lenders (BoB/PNB/Canara) read gross monthly income; we convert
      from net with a documented factor (estimated).
    * Self-employed: latest ITR / 12 if available, else net monthly income.
    """
    if app.employment_type == EmploymentType.SALARIED:
        if lender_id in GROSS_INCOME_LENDERS:
            return app.net_monthly_income * GROSS_FROM_NET, "gross"
        return app.net_monthly_income, "net"
    # self-employed
    if app.itr_income_y1:
        return app.itr_income_y1 / 12.0, "itr"
    return app.net_monthly_income, "net"


def itr_growth(app: Applicant) -> Optional[float]:
    """F33: (y1 - y2)/y2, None if fewer than 2 ITRs."""
    if app.itr_income_y1 is None or app.itr_income_y2 in (None, 0):
        return None
    return (app.itr_income_y1 - app.itr_income_y2) / app.itr_income_y2


def bureau_clean(app: Applicant) -> bool:
    """F32: no serious delinquency. True if (no DPD history OR DPD<30) AND no writeoff/settlement."""
    dpd_ok = app.max_dpd_last_12m is None or app.max_dpd_last_12m < 30
    return dpd_ok and not app.writeoff_or_settled_24m


def derive(app: Applicant, lender_id: str, product: str, segment: str) -> DerivedView:
    inc, mode = assessed_income(app, lender_id)
    obl = obligations(app)
    foir = obl / inc if inc > 0 else float("inf")
    return DerivedView(
        lender_id=lender_id,
        product=product,
        segment=segment,
        age_at_application=app.age_at_application,
        assessed_income=inc,
        income_mode=mode,
        total_obligations=obl,
        current_foir=foir,
        score_band=score_band(app.bureau_score),
        bureau_clean=bureau_clean(app),
        itr_income_growth=itr_growth(app),
        city_tier=lookups.city_tier(app.city),
        city_tier_band=lookups.tier_band(app.city),
    )


def max_tenure_by_age(age_at_application: float, maturity_cap_years: float,
                      product_max_months: int) -> int:
    """F25: largest tenure (months) that keeps age-at-maturity within the lender's cap."""
    headroom_months = int((maturity_cap_years - age_at_application) * 12)
    return max(0, min(product_max_months, headroom_months))
