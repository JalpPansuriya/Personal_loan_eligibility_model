"""Pydantic models: applicant input, parsed rule, and engine decision output.

Design notes
------------
* The applicant carries the 34 features from data/variables.csv (F01-F34) plus one
  optional feature, gender (F35), used only for rate concessions, never for eligibility.
* NULL discipline (adapted from the IBL leakage rule): bureau_score, max_dpd_last_12m,
  credit_history_months, business_vintage_months, and the ITR fields may be None and are
  NEVER silently coerced to 0. None means "not applicable / new to credit", which is
  semantically different from a real 0.
* Only existing_emi_monthly and credit_card_outstanding default to 0 (no loans genuinely
  means zero obligation).
* Derived features F23-F34 are NOT stored on the applicant; they are computed per lender
  in preprocess.py, because several (assessed income, FOIR, tenure cap) are lender-specific.
"""
from __future__ import annotations

import datetime as _dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------- enums
class EmploymentType(str, Enum):
    SALARIED = "salaried"
    SEP = "sep"   # self-employed professional (doctor, CA, ...)
    SEB = "seb"   # self-employed business


class Gender(str, Enum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class ResidenceType(str, Enum):
    OWNED = "owned"
    RENTED = "rented"
    COMPANY = "company"
    PARENTAL = "parental"


class MaritalStatus(str, Enum):
    SINGLE = "single"
    MARRIED = "married"
    WIDOW = "widow"
    DIVORCED = "divorced"


class Confidence(str, Enum):
    PUBLISHED = "published"
    PUBLISHED_CONFLICT = "published_conflict"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    ESTIMATED_SUPERSEDED = "estimated_superseded"


class Status(str, Enum):
    """Screening statuses. The engine evaluates published lender criteria; it does NOT
    issue bank approvals, so no status implies a guaranteed sanction."""
    ELIGIBLE_TO_QUERY_LENDERS = "ELIGIBLE_TO_QUERY_LENDERS"   # passes all mandatory rules + fully priced
    PRELIMINARILY_ELIGIBLE = "PRELIMINARILY_ELIGIBLE"         # passes rules; some terms estimated/reduced
    NOT_ELIGIBLE = "NOT_ELIGIBLE"                             # a documented mandatory rule is violated
    ADDITIONAL_INFORMATION_REQUIRED = "ADDITIONAL_INFORMATION_REQUIRED"  # a needed value is missing
    MANUAL_REVIEW = "MANUAL_REVIEW"                           # ambiguous/unverified condition
    INVALID_INPUT = "INVALID_INPUT"                           # applicant data failed validation
    RULES_UNAVAILABLE = "RULES_UNAVAILABLE"                   # insufficient rule data to decide

    @property
    def is_offer(self) -> bool:
        return self in (Status.ELIGIBLE_TO_QUERY_LENDERS, Status.PRELIMINARILY_ELIGIBLE)


LENDERS: tuple[str, ...] = (
    "sbi", "hdfc", "icici", "axis", "kotak", "bob", "pnb", "canara", "union", "indusind",
    "idfc", "yes", "bajaj", "tata", "abcl", "lnt", "poonawalla", "navi", "kreditbee", "moneyview",
)

# lender -> policy tier for the bureau-hygiene rules (agreed with user)
LENDER_TYPE: dict[str, str] = {
    "sbi": "bank", "hdfc": "bank", "icici": "bank", "axis": "bank", "kotak": "bank",
    "bob": "bank", "pnb": "bank", "canara": "bank", "union": "bank", "indusind": "bank",
    "idfc": "bank", "yes": "bank",
    "bajaj": "nbfc", "tata": "nbfc", "abcl": "nbfc", "lnt": "nbfc", "poonawalla": "nbfc",
    "navi": "fintech", "kreditbee": "fintech", "moneyview": "fintech",
}

# allowed requested tenures (months); clipped to each lender's own min/max later
ALLOWED_TENURES: tuple[int, ...] = (3, 6, 9, 12, 18, 24, 36, 48, 60, 72, 84, 96, 108)


# --------------------------------------------------------------------------- applicant
class Applicant(BaseModel):
    """One loan applicant. Field names follow data/variables.csv (F01-F34, +F35 gender).

    Raw features only. Derived (F23-F34) are computed in preprocess.py.
    """
    model_config = {"extra": "forbid"}

    # F01-F03 employment
    employment_type: EmploymentType
    employer_category: Optional[str] = None          # F02, free string -> mapped via lookup
    profession: Optional[str] = None                 # F03, sep only

    # F04-F06 experience / vintage
    total_experience_months: int = Field(0, ge=0)
    current_job_tenure_months: int = Field(0, ge=0)
    business_vintage_months: Optional[int] = Field(None, ge=0)

    # F07-F10 income
    net_monthly_income: float = Field(..., gt=0)
    itr_income_y1: Optional[float] = Field(None, ge=0)
    itr_income_y2: Optional[float] = Field(None, ge=0)
    itr_years_filed: int = Field(0, ge=0)

    # F11-F18 bureau
    existing_emi_monthly: float = Field(0, ge=0)
    credit_card_outstanding: float = Field(0, ge=0)
    bureau_score: Optional[int] = None               # None = NTC; else 300-900
    credit_history_months: Optional[int] = Field(None, ge=0)
    max_dpd_last_12m: Optional[int] = Field(None, ge=0)
    enquiries_last_6m: int = Field(0, ge=0)
    writeoff_or_settled_24m: bool = False
    active_unsecured_loans: int = Field(0, ge=0)

    # F19-F21 location / residence / relationship
    city: Optional[str] = None                       # resolved to tier via lookup
    residence_type: Optional[ResidenceType] = None
    residence_stability_months: Optional[int] = Field(None, ge=0)
    salary_account_with_lender: Optional[str] = None  # lender id or None

    # F22 optional request
    requested_tenure_months: Optional[int] = Field(None, ge=1)
    requested_amount: Optional[float] = Field(None, gt=0)

    # F35 optional, concession-only
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None

    # point-in-time
    date_of_birth: _dt.date
    application_date: _dt.date = Field(default_factory=_dt.date.today)

    @field_validator("bureau_score")
    @classmethod
    def _score_range(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v == 0:
            raise ValueError("bureau_score=0 is invalid; use None for new-to-credit")
        if not 300 <= v <= 900:
            raise ValueError(f"bureau_score {v} outside 300-900 (or None for NTC)")
        return v

    @field_validator("salary_account_with_lender")
    @classmethod
    def _salary_lender(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "none":
            return None
        if v not in LENDERS:
            raise ValueError(f"salary_account_with_lender {v!r} not a known lender id")
        return v

    @model_validator(mode="after")
    def _coherence(self) -> "Applicant":
        age_days = (self.application_date - self.date_of_birth).days
        if age_days <= 0:
            raise ValueError("date_of_birth must be before application_date")
        age = age_days / 365.25
        if not 18 <= age <= 80:
            raise ValueError(f"age {age:.1f} outside 18-80 at application")
        if self.net_monthly_income > 10_000_000:
            raise ValueError("net_monthly_income exceeds 1 crore/month; check units")
        if self.employment_type == EmploymentType.SALARIED and self.business_vintage_months:
            raise ValueError("salaried applicant should not have business_vintage_months")
        return self

    @property
    def age_at_application(self) -> float:
        """F23: exact age in years at application (never a stored integer)."""
        return (self.application_date - self.date_of_birth).days / 365.25

    @property
    def is_ntc(self) -> bool:
        return self.bureau_score is None


# --------------------------------------------------------------------------- rule
class Rule(BaseModel):
    """One atomic rule row from data/lender_rules_long.csv."""
    model_config = {"extra": "ignore"}

    rule_id: str
    lender_id: str
    product: str
    segment: str
    variable: str
    operator: str
    value: str
    unit: str = ""
    effect: str = ""
    condition: str = ""
    source_url: str = ""
    source_file: str = ""
    accessed_date: str = ""
    confidence: Confidence
    estimation_method: str = ""
    quote: str = ""
    notes: str = ""


# --------------------------------------------------------------------------- decision
class RuleStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    ESTIMATED = "ESTIMATED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


def rule_status_of(conf: Optional["Confidence"]) -> "RuleStatus":
    return {
        Confidence.PUBLISHED: RuleStatus.PUBLISHED,
        Confidence.PUBLISHED_CONFLICT: RuleStatus.PUBLISHED,
        Confidence.DERIVED: RuleStatus.DERIVED,
        Confidence.ESTIMATED: RuleStatus.ESTIMATED,
        Confidence.ESTIMATED_SUPERSEDED: RuleStatus.ESTIMATED,
    }.get(conf, RuleStatus.UNKNOWN)


class ReasonCode(BaseModel):
    """One line in a lender decision's explanation chain (machine code + human text)."""
    code: str
    variable: str = ""
    message: str
    rule_id: str = ""
    applicant_value: Optional[str] = None
    required_value: Optional[str] = None
    rule_status: RuleStatus = RuleStatus.UNKNOWN
    confidence: Optional[Confidence] = None
    source_url: str = ""
    next_action: str = ""


class Fix(BaseModel):
    """A single counterfactual action that would change a rejection to eligibility."""
    lever: str                 # emi_reduction | income_increase | tenure | wait_months | lender
    description: str
    amount: Optional[float] = None
    unit: str = ""


class AmountQuote(BaseModel):
    """A principal with its tenure and the EMI for THAT principal/tenure (never mixed)."""
    amount: Optional[float] = None
    tenure_months: Optional[int] = None
    emi: Optional[float] = None


class CapBreakdown(BaseModel):
    """Every computed limit on the max eligible amount, and which one bound."""
    foir: Optional[float] = None
    take_home: Optional[float] = None
    multiple: Optional[float] = None
    product: Optional[float] = None
    calculator: Optional[float] = None
    binding_cap: str = ""      # foir | take_home | multiple | product | calculator


class PricingBreakdown(BaseModel):
    """Interest rate, fees, GST and APR kept strictly separate (§4)."""
    nominal_rate_pa: Optional[float] = None
    rate_is_range: bool = False
    rate_min_pa: Optional[float] = None
    rate_max_pa: Optional[float] = None
    rate_source: str = ""              # grid_range | repriced | published_range
    rate_confidence: Optional[Confidence] = None
    rate_source_url: str = ""
    rate_accessed_date: str = ""
    processing_fee: Optional[float] = None      # fee ex-GST
    gst_on_fee: Optional[float] = None          # 18% of fee
    other_charges: Optional[float] = None
    net_disbursement: Optional[float] = None    # principal - fee - GST (upfront-deducted)
    total_repayment: Optional[float] = None     # EMI * n
    total_cost_of_credit: Optional[float] = None  # total_repayment + fee + GST - principal
    apr_pa: Optional[float] = None
    apr_available: bool = True
    apr_note: str = ""


class LenderOffer(BaseModel):
    """The engine's screening result for one lender/product for one applicant.

    requested_* and max_eligible_* are kept strictly separate; every EMI lives inside an
    AmountQuote next to the principal and tenure it was computed for (§2/§3)."""
    lender_id: str
    product: str
    product_label: str = ""
    segment: str
    status: Status

    requested: AmountQuote = Field(default_factory=AmountQuote)      # requested amount/tenure/EMI
    max_eligible: AmountQuote = Field(default_factory=AmountQuote)   # max amount, its tenure, its EMI
    requested_supported: bool = False     # does the max cover the requested amount?

    caps: CapBreakdown = Field(default_factory=CapBreakdown)
    pricing: PricingBreakdown = Field(default_factory=PricingBreakdown)

    strength_score: Optional[int] = None
    reasons: list[ReasonCode] = Field(default_factory=list)
    fixes: list[Fix] = Field(default_factory=list)
    rationale: str = ""
    lowest_confidence: Optional[Confidence] = None


class Decision(BaseModel):
    """The full engine result for one applicant across all lenders."""
    eligible: bool                       # at least one offer the applicant can take to a lender
    offers: list[LenderOffer] = Field(default_factory=list)
    best_offer: Optional[LenderOffer] = None
    best_rationale: str = ""
    top_blocking_reasons: list[ReasonCode] = Field(default_factory=list)
    applicant_age: float = 0.0
    disclaimer: str = ("Preliminary screening against published lender criteria. "
                       "Estimates only, not loan offers; actual approval depends on each "
                       "lender's internal checks.")
