"""Approval-strength score 0-100 (scorecard with published weights).

Weights (from model_report.md section 8.8, fixed by underwriting judgement, NOT optimised):
    score margin            30
    FOIR headroom           25
    stability / experience  15
    bureau hygiene          15
    relationship / employer 10
    amount-vs-multiple slack 5

The score is informational: it NEVER turns a gate failure into an approval. The engine
only computes it for offers that already passed the gates. Bands:
    >=75 strong | 50-74 comfortable | 30-49 borderline | <30 weak-but-passing
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
        return "strong"
    if score >= 50:
        return "comfortable"
    if score >= 30:
        return "borderline"
    return "weak-but-passing"
