"""Engine orchestration: evaluate every lender/product for an applicant.

For each lender -> each product offering the applicant's segment:
  1. derive features
  2. run hard gates (incl tiered bureau policy)
  3. route the result into a screening status:
       NOT_ELIGIBLE                     a documented mandatory rule is violated
       ADDITIONAL_INFORMATION_REQUIRED  a needed value is missing (e.g. SE vintage)
       MANUAL_REVIEW                    an ambiguous/unverified condition (e.g. check-off)
       ELIGIBLE_TO_QUERY_LENDERS        passes all rules + fully priced on published data
       PRELIMINARILY_ELIGIBLE           passes rules but some terms estimated/reduced
  4. for eligible routes: size the max loan (cap breakdown), compute the EMI for the
     REQUESTED amount and separately the EMI for the MAX ELIGIBLE amount, and price both
     with fees/GST/APR kept separate.
Then pick the best eligible option on the requested terms, with a rationale.

Deterministic: no randomness, stable tie-breaks (APR, then strength, then lender id).
The engine screens published criteria; it never asserts a bank approval.
"""
from __future__ import annotations

from typing import Optional

from . import affordability as af
from . import preprocess as pp
from . import pricing as pr
from . import strength as st
from .gates import GateResult, GateEvaluator
from .rules import RuleStore, get_store
from .schema import (AmountQuote, Applicant, CapBreakdown, Confidence, Decision,
                     Gender, LenderOffer, ReasonCode, RuleStatus, Status)

CONF_RANK = {Confidence.PUBLISHED: 0, Confidence.PUBLISHED_CONFLICT: 1, Confidence.DERIVED: 2,
             Confidence.ESTIMATED: 3, Confidence.ESTIMATED_SUPERSEDED: 4}

# status preference when choosing between products of one lender / ranking
STATUS_RANK = {
    Status.ELIGIBLE_TO_QUERY_LENDERS: 0,
    Status.PRELIMINARILY_ELIGIBLE: 1,
    Status.MANUAL_REVIEW: 2,
    Status.ADDITIONAL_INFORMATION_REQUIRED: 3,
    Status.NOT_ELIGIBLE: 4,
    Status.RULES_UNAVAILABLE: 5,
}


def _product_label(product: str) -> str:
    return product.replace("_", " ").title()


class Engine:
    def __init__(self, store: Optional[RuleStore] = None):
        self.store = store or get_store()
        self.gates = GateEvaluator(self.store)

    # ------------------------------------------------------------------ tenure
    def _tenure(self, app: Applicant, product: str, segment: str, lender: str,
                d: pp.DerivedView, *, for_max: bool = False) -> int:
        pmin = af._resolve_value(self.store, lender, product, segment, "tenure_min_months", pick_min=False) or 12
        pmax = af._resolve_value(self.store, lender, product, segment, "tenure_max_months", pick_min=True) or 60
        mat = af._resolve_value(self.store, lender, product, segment, "age_max_at_maturity", pick_min=True)
        cap = int(pmax)
        if mat is not None:
            cap = pp.max_tenure_by_age(d.age_at_application, mat, int(pmax))
        if app.requested_tenure_months and not for_max:
            want = app.requested_tenure_months
        else:
            # max-eligibility uses the longest permitted tenure (most affordability room)
            want = cap
        return max(int(pmin), min(want, cap))

    # ------------------------------------------------------------------ per lender/product
    def evaluate_product(self, app: Applicant, lender: str, product: str, segment: str) -> LenderOffer:
        d = pp.derive(app, lender, product, segment)
        gate = self.gates.evaluate(app, product, segment, lender, d)
        offer = LenderOffer(lender_id=lender, product=product, product_label=_product_label(product),
                            segment=segment, status=Status.NOT_ELIGIBLE)

        # 1. confirmed mandatory violation -> NOT_ELIGIBLE
        if gate.reasons:
            offer.status = Status.NOT_ELIGIBLE
            offer.reasons = gate.reasons + gate.missing_info + gate.review
            offer.lowest_confidence = self._lowest_conf(gate.reasons)
            return offer

        # 2/3. no violation, but needed info missing / ambiguous -> info-required / review
        if gate.missing_info:
            offer.status = Status.ADDITIONAL_INFORMATION_REQUIRED
            offer.reasons = gate.missing_info + gate.review
            return offer
        if gate.review:
            offer.status = Status.MANUAL_REVIEW
            offer.reasons = gate.review
            return offer

        # 4. eligible: compute tenures (requested vs max), size, price both
        req_tenure = self._tenure(app, product, segment, lender, d, for_max=False)
        max_tenure = self._tenure(app, product, segment, lender, d, for_max=True)
        if req_tenure < 1 or max_tenure < 1:
            offer.status = Status.NOT_ELIGIBLE
            offer.reasons = [ReasonCode(code="AGE_AT_MATURITY", variable="age_max_at_maturity",
                                        message="no tenure fits the maturity cap",
                                        rule_id=f"{lender}-maturity", rule_status=RuleStatus.PUBLISHED,
                                        next_action="Choose a lender with a higher maturity age.")]
            return offer

        band = d.score_band
        is_female = app.gender == Gender.FEMALE
        prelim_rate, _ = pr.nominal_rate(self.store, lender, product, segment, band, is_female=is_female)

        # size the MAX eligible amount at the max tenure (most affordability room)
        sizing = af.size_loan(self.store, app, d, product, segment, prelim_rate, max_tenure)
        max_loan = sizing.max_loan
        if "reprice_nbfc" in gate.bureau_soft_flags:
            max_loan *= 0.5
        elif "reprice_fintech" in gate.bureau_soft_flags:
            max_loan *= 0.4
        max_loan = af.floor_to(max_loan, 1000)

        pmin = af.product_min(self.store, lender, product, segment) or 0
        if max_loan < max(pmin, 1000):
            offer.status = Status.NOT_ELIGIBLE
            offer.reasons = [ReasonCode(code="AMOUNT_BELOW_MIN", variable="loan_min",
                                        message="eligible amount below product minimum",
                                        rule_id=f"{lender}-{product}", applicant_value=str(max_loan),
                                        required_value=str(max(pmin, 1000)), rule_status=RuleStatus.PUBLISHED,
                                        next_action="Not affordable at this income/obligation level.")]
            return offer

        offer.caps = CapBreakdown(
            foir=sizing.caps.get("foir"), take_home=sizing.caps.get("take_home"),
            multiple=sizing.caps.get("multiple"), product=sizing.caps.get("product"),
            calculator=sizing.caps.get("calculator"), binding_cap=sizing.binding_cap,
        )

        # requested amount quote (clamped to max): EMI for the REQUESTED principal/tenure
        requested_amount = app.requested_amount
        requested_supported = requested_amount is None or max_loan >= requested_amount - 1
        offered_requested = min(requested_amount, max_loan) if requested_amount else None

        # pricing on the requested amount (or on max if none requested) at the REQUESTED tenure
        price_amount = offered_requested if offered_requested else max_loan
        price_tenure = req_tenure
        pricing, req_emi = pr.price_full(self.store, lender, product, segment, band,
                                         price_amount, price_tenure, is_female=is_female,
                                         bureau_soft_flags=gate.bureau_soft_flags)
        offer.pricing = pricing

        # separate EMI for the MAX eligible amount at the MAX tenure
        from .finance import emi as _emi
        max_emi = round(_emi(max_loan, pricing.nominal_rate_pa, max_tenure), 2)

        offer.requested = AmountQuote(
            amount=offered_requested if requested_amount else None,
            tenure_months=req_tenure if requested_amount else None,
            emi=req_emi if requested_amount else None,
        )
        offer.max_eligible = AmountQuote(amount=max_loan, tenure_months=max_tenure, emi=max_emi)
        offer.requested_supported = bool(requested_supported)

        fl = af.foir_limit(self.store, lender, product, segment)
        offer.strength_score = st.strength(app, d, lender, fl, max_loan)
        offer.lowest_confidence = pricing.rate_confidence or Confidence.PUBLISHED

        # status: passes all mandatory rules on published pricing and covers the requested
        # amount -> ELIGIBLE. A published rate *band* (min..max) still counts as eligible; it
        # is only "preliminary" when the rate is estimated, the amount was reduced/repriced,
        # or the requested amount is not covered.
        rate_pub = pricing.rate_confidence in (Confidence.PUBLISHED, Confidence.PUBLISHED_CONFLICT)
        if gate.bureau_soft_flags or not requested_supported or not rate_pub:
            offer.status = Status.PRELIMINARILY_ELIGIBLE
        else:
            offer.status = Status.ELIGIBLE_TO_QUERY_LENDERS

        if gate.bureau_soft_flags:
            offer.reasons.append(ReasonCode(
                code="REPRICED", variable="bureau_reject_signal",
                message="terms repriced and amount reduced due to bureau signals",
                rule_status=RuleStatus.ESTIMATED, confidence=Confidence.ESTIMATED,
                next_action="Improve the bureau profile for standard pricing."))
        return offer

    def _lowest_conf(self, reasons: list[ReasonCode]) -> Optional[Confidence]:
        confs = [r.confidence for r in reasons if r.confidence]
        return max(confs, key=lambda c: CONF_RANK[c]) if confs else None

    # ------------------------------------------------------------------ full run
    def run(self, app: Applicant) -> Decision:
        segment = app.employment_type.value
        offers: list[LenderOffer] = []
        for lender in self.store.lenders():
            best_for_lender: Optional[LenderOffer] = None
            for product in self.store.products_for_segment(lender, segment):
                off = self.evaluate_product(app, lender, product, segment)
                best_for_lender = _prefer(best_for_lender, off)
            if best_for_lender is not None:
                offers.append(best_for_lender)

        eligible = [o for o in offers if o.status.is_offer]
        best, rationale = _best_offer(eligible, app)
        decision = Decision(
            eligible=bool(eligible),
            offers=offers,
            best_offer=best,
            best_rationale=rationale,
            applicant_age=round(app.age_at_application, 1),
        )
        if best:
            best.rationale = rationale
        if not eligible:
            decision.top_blocking_reasons = _top_reasons(offers)
        return decision


def _prefer(a: Optional[LenderOffer], b: LenderOffer) -> LenderOffer:
    """Prefer the better of two product offers from the same lender."""
    if a is None:
        return b
    if STATUS_RANK[b.status] != STATUS_RANK[a.status]:
        return b if STATUS_RANK[b.status] < STATUS_RANK[a.status] else a
    if not a.status.is_offer:
        return a
    # same offer status: prefer lower APR, then larger max eligible
    ba, aa = (b.pricing.apr_pa or 1e9), (a.pricing.apr_pa or 1e9)
    if ba != aa:
        return b if ba < aa else a
    return a


def _best_offer(eligible: list[LenderOffer], app: Applicant) -> tuple[Optional[LenderOffer], str]:
    """Rank eligible options on the requested terms. Returns (best, rationale)."""
    if not eligible:
        return None, ""
    # prefer options that actually cover the requested amount
    covering = [o for o in eligible if o.requested_supported]
    pool = covering or eligible
    ranked = sorted(pool, key=lambda o: (o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9,
                                         -(o.strength_score or 0), o.lender_id))
    best = ranked[0]
    note = "covering the requested amount" if (covering and best in covering) else \
           "offering the largest affordable amount"
    rationale = (f"Lowest APR ({best.pricing.apr_pa}%) among {len(pool)} eligible products "
                 f"{note}; nominal rate {best.pricing.nominal_rate_pa}%, "
                 f"strength {best.strength_score}/100.")
    return best, rationale


def _top_reasons(offers: list[LenderOffer]) -> list[ReasonCode]:
    from collections import Counter
    counter: Counter = Counter()
    sample: dict[str, ReasonCode] = {}
    for o in offers:
        for r in o.reasons:
            counter[r.code] += 1
            sample.setdefault(r.code, r)
    return [sample[code] for code, _ in counter.most_common(5)]
