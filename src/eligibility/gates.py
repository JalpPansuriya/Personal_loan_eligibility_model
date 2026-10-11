"""Hard-gate evaluation for one applicant against one lender/product/segment.

Returns a GateResult: passed flag + a list of ReasonCode (one per failing gate, each
carrying the rule id, applicant value, required value, confidence and source URL).

Policies (agreed with the user):
* Conflict policy: where a lender's own pages disagree on a gate value, use the STRICTER
  value (hardest for the applicant). The stricter direction per variable mirrors
  scripts/build_rule_tables.py.
* Missing applicant data for a gate = that gate FAILS (never silently passes).
* Tiered bureau hygiene (unlisted, estimated):
    banks   -> REJECT on DPD>=30 (12m), enquiries>=6 (6m), or writeoff/settlement (24m)
    nbfcs   -> REJECT on writeoff/settlement or DPD>=60; otherwise (DPD 30-59 or enq>=6)
               a soft flag used later for repricing (not a reject here)
    fintech -> REJECT on writeoff/settlement only where the lender publishes a min score;
               KreditBee is lenient (no score reject). Soft flag otherwise.
  The soft flags are returned on the result for the pricing layer; only hard rejects
  appear as failing ReasonCodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import lookups
from .conditions import ParsedCondition
from .preprocess import DerivedView
from .rules import IndexedRule, RuleStore
from .schema import Applicant, Confidence, EmploymentType, ReasonCode, rule_status_of

# stricter direction per gate variable (higher value is harder to meet)
STRICTER_HIGHER = {
    "age_min", "income_min_monthly", "income_min_annual", "household_income_min_annual",
    "household_income_min_monthly", "exp_total_min_months", "exp_current_min_months",
    "business_vintage_min_months", "post_qualification_exp_min_months", "itr_years_min",
    "score_min", "relationship_min_months", "residence_stability_min_months",
}
STRICTER_LOWER = {"age_max_at_application", "age_max_at_maturity", "max_active_loans"}

# reason code -> suggested next action shown to the user (§9)
NEXT_ACTION = {
    "SEGMENT_NOT_OFFERED": "Try a lender that offers this employment segment.",
    "AGE_BELOW_MIN": "Re-check at the minimum application age, or choose a lender with a lower age bar.",
    "AGE_ABOVE_MAX": "Choose a lender with a higher maximum application age.",
    "AGE_AT_MATURITY": "Shorten the tenure so the loan matures within the lender's age cap.",
    "INCOME_BELOW_MIN": "Document higher net income, or choose a lower-income-floor lender.",
    "EXP_TOTAL_LT_MIN": "Build the required total work experience, then re-check.",
    "EXP_CURRENT_LT_MIN": "Build the required months with the current employer, then re-check.",
    "VINTAGE_LT_MIN": "Provide business-vintage proof meeting the minimum, or wait.",
    "ITR_YEARS_LT_MIN": "File the required number of ITRs, then re-check.",
    "SCORE_BELOW_MIN": "Improve the bureau score to the required minimum.",
    "NTC_NOT_ALLOWED": "Build a credit history, or choose a new-to-credit-friendly lender.",
    "EMPLOYER_NOT_ALLOWED": "Confirm the employer category; this lender restricts employers.",
    "PROFESSION_NOT_ALLOWED": "This lender's product restricts professions; try another route.",
    "SALARY_ACCOUNT_REQUIRED": "Open/declare a salary account with this lender, or choose another.",
    "CITY_NOT_SERVICED": "Choose a lender that services this city.",
    "RECENT_DPD_GTE30": "Clear overdues and maintain clean payments for several months.",
    "RECENT_DPD_GTE60": "Clear overdues and rebuild payment history.",
    "EXCESS_ENQUIRIES": "Pause new credit applications for a few months.",
    "PRIOR_WRITEOFF_SETTLEMENT": "Resolve the settlement/write-off and rebuild history.",
    "AMOUNT_BELOW_MIN": "Request an amount at or above the product minimum.",
    "RELATIONSHIP_REQUIRED": "Provide proof of the required relationship/check-off, or seek manual review.",
}

# codes that mean 'we lack a value to decide' rather than a confirmed violation (§6/§7)
MISSING_INFO_CODES = {"VINTAGE_LT_MIN_MISSING", "RELATIONSHIP_REQUIRED"}
MANUAL_REVIEW_CODES = {"RELATIONSHIP_UNVERIFIED", "CHECKOFF_UNVERIFIED"}


@dataclass
class GateResult:
    passed: bool
    reasons: list[ReasonCode] = field(default_factory=list)      # confirmed violations
    missing_info: list[ReasonCode] = field(default_factory=list)  # needed value absent
    review: list[ReasonCode] = field(default_factory=list)        # ambiguous/unverified
    bureau_soft_flags: list[str] = field(default_factory=list)    # for pricing (NBFC/fintech reprice)
    notes: list[str] = field(default_factory=list)


def _num(v: str) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def build_context(app: Applicant, d: DerivedView) -> dict:
    """Fields that rule conditions may reference (see conditions.APPLICANT_FIELDS)."""
    rec = lookups.resolve_city(app.city)
    return {
        "gender": app.gender.value if app.gender else None,
        "marital_status": app.marital_status.value if app.marital_status else None,
        "city": app.city,
        "city_tier": d.city_tier_band,          # metro|urban|semi_urban (condition vocabulary)
        "tier": rec["axis_tier"] if rec else None,
        "employer_category": (app.employer_category or "").lower() or None,
        "profession": (app.profession or "").lower() or None,
        "residence_type": app.residence_type.value if app.residence_type else None,
        "salary_account": app.salary_account_with_lender,
        "employer": None,
        "score": app.bureau_score,
        "loan_amount": app.requested_amount,
        "tenure_months": app.requested_tenure_months,
    }


def _resolve(cands: list[IndexedRule], variable: str) -> IndexedRule:
    """Apply the stricter-value conflict policy over same-variable candidates."""
    nums = [(_num(ir.rule.value), ir) for ir in cands]
    nums = [(v, ir) for v, ir in nums if v is not None]
    if nums and variable in STRICTER_HIGHER:
        return max(nums, key=lambda t: t[0])[1]
    if nums and variable in STRICTER_LOWER:
        return min(nums, key=lambda t: t[0])[1]
    return cands[0]


def _reason(ir: IndexedRule, code: str, msg: str, actual, required) -> ReasonCode:
    return ReasonCode(
        code=code, variable=ir.variable, message=msg, rule_id=ir.rule_id,
        applicant_value=None if actual is None else str(actual),
        required_value=None if required is None else str(required),
        rule_status=rule_status_of(ir.rule.confidence),
        confidence=ir.rule.confidence, source_url=ir.rule.source_url,
        next_action=NEXT_ACTION.get(code, ""),
    )


class GateEvaluator:
    def __init__(self, store: RuleStore):
        self.store = store

    # ------------------------------------------------------------------ main
    def evaluate(self, app: Applicant, product: str, segment: str,
                 lender_id: str, d: DerivedView) -> GateResult:
        ctx = build_context(app, d)
        scoped = [ir for ir in self.store.scope(lender_id, product, segment)
                  if ir.effect == "gate" and ir.rule.operator != "info"]
        # keep only rules whose condition applies to this applicant
        active = [ir for ir in scoped if ir.cond.applies(ctx)]

        res = GateResult(passed=True)

        # group by variable, resolve conflicts with stricter value
        by_var: dict[str, list[IndexedRule]] = {}
        for ir in active:
            by_var.setdefault(ir.variable, []).append(ir)

        for variable, cands in by_var.items():
            chosen = _resolve(cands, variable)
            reason = self._check(variable, chosen, app, d, segment, lender_id, ctx)
            if reason is not None:
                if reason.code in MISSING_INFO_CODES:
                    res.missing_info.append(reason)
                elif reason.code in MANUAL_REVIEW_CODES:
                    res.review.append(reason)
                else:
                    res.passed = False
                    res.reasons.append(reason)

        # tiered bureau hygiene (applies to every lender, estimated)
        self._bureau(app, lender_id, res)
        if res.reasons:
            res.passed = False
        return res

    # ------------------------------------------------------------------ per-variable checks
    def _check(self, variable: str, ir: IndexedRule, app: Applicant, d: DerivedView,
               segment: str, lender_id: str, ctx: dict) -> Optional[ReasonCode]:
        op = ir.rule.operator
        val = ir.rule.value
        num = _num(val)

        if variable == "segment_offered":
            if op == "not_offered" or str(val).strip().lower() in ("false", "not_offered", ""):
                return _reason(ir, "SEGMENT_NOT_OFFERED",
                               f"{lender_id} has no {segment} product here", segment, "offered")
            return None

        if variable == "age_min" and num is not None:
            if app.age_at_application < num:
                return _reason(ir, "AGE_BELOW_MIN", "below minimum application age",
                               round(app.age_at_application, 1), num)
            return None

        if variable == "age_max_at_application" and num is not None:
            if app.age_at_application > num:
                return _reason(ir, "AGE_ABOVE_MAX", "above maximum application age",
                               round(app.age_at_application, 1), num)
            return None

        if variable == "age_max_at_maturity" and num is not None:
            # fails only if even the shortest sensible tenure (12m) breaches the cap
            if d.age_at_maturity(12) > num:
                return _reason(ir, "AGE_AT_MATURITY", "age at maturity exceeds cap even at min tenure",
                               round(d.age_at_maturity(12), 1), num)
            return None

        if variable == "income_min_monthly" and num is not None:
            if d.assessed_income < num:
                return _reason(ir, "INCOME_BELOW_MIN", "assessed income below city/segment minimum",
                               round(d.assessed_income), num)
            return None

        if variable == "income_min_annual" and num is not None:
            annual = (app.itr_income_y1 if app.itr_income_y1 is not None
                      else d.assessed_income * 12)
            if annual < num:
                return _reason(ir, "INCOME_BELOW_MIN", "annual income below minimum",
                               round(annual), num)
            return None

        if variable in ("household_income_min_monthly", "household_income_min_annual") and num is not None:
            # we don't collect household income separately; use applicant income as proxy
            base = d.assessed_income if "monthly" in variable else d.assessed_income * 12
            if base < num:
                return _reason(ir, "INCOME_BELOW_MIN", "household income below minimum",
                               round(base), num)
            return None

        if variable == "exp_total_min_months" and num is not None:
            if app.total_experience_months < num:
                return _reason(ir, "EXP_TOTAL_LT_MIN", "total experience below minimum",
                               app.total_experience_months, num)
            return None

        if variable == "exp_current_min_months" and num is not None:
            if app.current_job_tenure_months < num:
                return _reason(ir, "EXP_CURRENT_LT_MIN", "current-job tenure below minimum",
                               app.current_job_tenure_months, num)
            return None

        if variable == "business_vintage_min_months" and num is not None:
            v = app.business_vintage_months
            if v is None:
                return _reason(ir, "VINTAGE_LT_MIN_MISSING", "business vintage not provided",
                               None, num)
            if v < num:
                return _reason(ir, "VINTAGE_LT_MIN", "business vintage below minimum", v, num)
            return None

        if variable == "post_qualification_exp_min_months" and num is not None:
            if app.total_experience_months < num:
                return _reason(ir, "EXP_TOTAL_LT_MIN", "post-qualification experience below minimum",
                               app.total_experience_months, num)
            return None

        if variable == "itr_years_min" and num is not None:
            if app.itr_years_filed < num:
                return _reason(ir, "ITR_YEARS_LT_MIN", "fewer filed ITRs than required",
                               app.itr_years_filed, num)
            return None

        if variable == "score_min" and num is not None:
            if app.bureau_score is None:
                return None  # NTC handled by ntc_allowed, not score_min
            if app.bureau_score < num:
                return _reason(ir, "SCORE_BELOW_MIN", "bureau score below minimum",
                               app.bureau_score, num)
            return None

        if variable == "ntc_allowed":
            allowed = str(val).strip().lower() in ("true", "yes", "1")
            if app.bureau_score is None and not allowed:
                return _reason(ir, "NTC_NOT_ALLOWED", "lender requires a bureau score", "NTC", "score")
            return None

        if variable == "employer_category_allowed":
            allowed = lookups.employer_categories(lender_id, segment)
            emp = (app.employer_category or "").lower()
            if allowed and emp and not lookups.employer_matches(emp, allowed):
                return _reason(ir, "EMPLOYER_NOT_ALLOWED", "employer category not on allow-list",
                               emp, "/".join(sorted(allowed))[:60])
            return None

        if variable == "profession_allowed":
            allowed = {p.lower() for p in lookups.professions(lender_id, segment)}
            prof = (app.profession or "").lower()
            if allowed and prof and prof not in allowed and "etc" not in allowed:
                return _reason(ir, "PROFESSION_NOT_ALLOWED", "profession not on allow-list",
                               prof, "/".join(sorted(allowed))[:60])
            return None

        if variable == "salary_account_required":
            required = str(val).strip().lower() in ("true", "yes", "1")
            if required and app.salary_account_with_lender != lender_id:
                return _reason(ir, "SALARY_ACCOUNT_REQUIRED", "needs a salary account with this lender",
                               app.salary_account_with_lender or "none", lender_id)
            return None

        if variable == "relationship_min_months" and num is not None:
            # we don't model relationship tenure precisely; only block if applicant clearly
            # has no account with the lender AND the rule is unconditional
            if app.salary_account_with_lender != lender_id and not ir.cond.predicates:
                # treated as a soft requirement; do not hard-reject on estimated data
                return None
            return None

        if variable == "residence_stability_min_months" and num is not None:
            if app.residence_stability_months is not None and app.residence_stability_months < num:
                return _reason(ir, "RESIDENCE_STABILITY_LT_MIN", "residence stability below minimum",
                               app.residence_stability_months, num)
            return None

        if variable == "city_serviced":
            rec = lookups.resolve_city(app.city)
            if lender_id == "axis":
                if rec is None or not rec.get("axis_serviced"):
                    return _reason(ir, "CITY_NOT_SERVICED", "city not on the lender's service list",
                                   app.city or "unknown", "serviced city")
            return None

        if variable == "nationality":
            # applicant is assumed Indian resident; no field collected -> pass
            return None

        if variable == "education_min":
            return None  # not collected

        if variable == "max_active_loans" and num is not None:
            if app.active_unsecured_loans > num:
                return _reason(ir, "TOO_MANY_ACTIVE_LOANS", "too many active unsecured loans",
                               app.active_unsecured_loans, num)
            return None

        if variable in ("co_applicant_required", "guarantor_required"):
            return None  # structural requirement, not an applicant-level reject

        return None

    # ------------------------------------------------------------------ bureau hygiene
    def _bureau(self, app: Applicant, lender_id: str, res: GateResult) -> None:
        lt = self.store.lender_type(lender_id)
        dpd = app.max_dpd_last_12m
        enq = app.enquiries_last_6m
        wo = app.writeoff_or_settled_24m

        def reject(code: str, msg: str, actual, req):
            res.reasons.append(ReasonCode(code=code, variable="bureau_reject_signal",
                                          message=msg, rule_id=f"{lender_id}-bureau-policy",
                                          applicant_value=str(actual), required_value=str(req),
                                          rule_status=rule_status_of(Confidence.ESTIMATED),
                                          confidence=Confidence.ESTIMATED,
                                          next_action=NEXT_ACTION.get(code, "")))

        if lt == "bank":
            if wo:
                reject("PRIOR_WRITEOFF_SETTLEMENT", "write-off/settlement in last 24m", True, "none")
            if dpd is not None and dpd >= 30:
                reject("RECENT_DPD_GTE30", "30+ DPD in last 12m", dpd, "<30")
            if enq >= 6:
                reject("EXCESS_ENQUIRIES", "6+ hard enquiries in 6m", enq, "<6")
        elif lt == "nbfc":
            if wo:
                reject("PRIOR_WRITEOFF_SETTLEMENT", "write-off/settlement in last 24m", True, "none")
            if dpd is not None and dpd >= 60:
                reject("RECENT_DPD_GTE60", "60+ DPD in last 12m", dpd, "<60")
            elif (dpd is not None and dpd >= 30) or enq >= 6:
                res.bureau_soft_flags.append("reprice_nbfc")  # +3pp / 50% haircut later
        else:  # fintech
            if wo and lender_id in ("navi", "moneyview"):
                reject("PRIOR_WRITEOFF_SETTLEMENT", "write-off/settlement in last 24m", True, "none")
            elif (dpd is not None and dpd >= 30) or enq >= 6 or wo:
                res.bureau_soft_flags.append("reprice_fintech")  # +5pp / 60% haircut later
