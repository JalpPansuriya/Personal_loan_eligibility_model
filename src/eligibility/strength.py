"""Rule-fit score 0-100 (transparent, documented) — NOT an approval probability.

plan2 §9 requires the old "strength" score to be either removed or redefined as a
transparent, documented rule-match / data-completeness score, kept separate from
affordability and ranking, and never presented as an approval likelihood.

This score measures HOW WELL an applicant fits a product's published criteria and HOW
COMPLETE the inputs are — a comfort/fit indicator for a passing applicant. It is computed
only for offers that already passed every hard gate, so it can never turn a rejection into
an offer, and it is NOT used to rank offers (ranking uses APR/EMI/cost — see engine._best_offer).

Component weights (fixed by underwriting judgement, not optimised against any approval label,
because no approval labels exist):
    score margin            30   how far the bureau score sits above a 650 floor
    FOIR headroom           25   how far current FOIR sits below the lender's limit
    stability / experience  15   total work experience toward 60 months
    bureau hygiene          15   clean history vs DPD/enquiries
    relationship            10   existing salary-account relationship with the lender
    amount slack             5   requested amount vs the max this product supports

Bands: >=75 strong-fit | 50-74 comfortable-fit | 30-49 borderline-fit | <30 weak-but-passing.
"""
from __future__ import annotations

from .preprocess import DerivedView
from .schema import Applicant

WEIGHTS = {
    "score_margin": 30,
    "foir_headroom": 25,
    "stability": 15,
    "bureau": 15,
    "relationship": 10,
    "amount_slack": 5,
}

SCORE_METHOD = (
    "Rule-fit score (0-100): a weighted measure of how well the applicant fits this "
    "product's published criteria and how complete the inputs are. It is NOT an approval "
    "probability and does not affect offer ranking."
)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def strength(app: Applicant, d: DerivedView, lender_id: str, foir_limit: float | None,
             max_loan: float | None) -> int:
    # score margin: NTC scores low-middling; else distance above 650 up to 850
    if app.bureau_score is None:
        s_score = 0.35
    else:
        s_score = _clamp01((app.bureau_score - 650) / (850 - 650))

    # FOIR headroom: how far current FOIR sits below the lender's limit
    fl = foir_limit if foir_limit is not None else 0.60
    s_foir = _clamp01((fl - d.current_foir) / fl) if fl > 0 else 0.0

    # stability: total experience toward 60 months
    s_stab = _clamp01(app.total_experience_months / 60.0)

    # bureau hygiene: clean = full marks, else scaled by DPD/enquiries
    if not d.bureau_clean:
        s_bureau = 0.0
    else:
        enq_penalty = _clamp01(app.enquiries_last_6m / 6.0)
        s_bureau = 1.0 - 0.5 * enq_penalty

    # relationship / employer
    s_rel = 1.0 if app.salary_account_with_lender == lender_id else 0.3

    # amount-vs-multiple slack: requested vs max loan
    if app.requested_amount and max_loan:
        s_slack = _clamp01(1.0 - app.requested_amount / max_loan)
    else:
        s_slack = 0.5

    total = (WEIGHTS["score_margin"] * s_score + WEIGHTS["foir_headroom"] * s_foir
             + WEIGHTS["stability"] * s_stab + WEIGHTS["bureau"] * s_bureau
             + WEIGHTS["relationship"] * s_rel + WEIGHTS["amount_slack"] * s_slack)
    return int(round(total))


def band(score: int) -> str:
    if score >= 75:
        return "strong-fit"
    if score >= 50:
        return "comfortable-fit"
    if score >= 30:
        return "borderline-fit"
    return "weak-but-passing"
