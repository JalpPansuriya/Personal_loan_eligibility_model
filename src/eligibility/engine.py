"""Engine orchestration: evaluate every lender/product for an applicant.

For each lender -> each product offering the applicant's segment:
  1. derive features
  2. run hard gates (incl tiered bureau policy)
  3. route the result into a screening status:
       NOT_ELIGIBLE                     a documented mandatory rule is violated
       ADDITIONAL_INFORMATION_REQUIRED  a needed value is missing (e.g. SE vintage)
       MANUAL_REVIEW                    an ambiguous/unverified condition (e.g. check-off)
       ELIGIBLE_FOR_REQUESTED_TERMS     passes all rules + covers the exact requested amount/tenure
       ELIGIBLE_FOR_ALTERNATIVE_TERMS   passes rules but only a smaller amount / shorter tenure fits
       PRELIMINARILY_ELIGIBLE           passes rules but some terms estimated/repriced/undetermined
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
    Status.ELIGIBLE_FOR_REQUESTED_TERMS: 0,
    Status.PRELIMINARILY_ELIGIBLE: 1,
    Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS: 2,
    Status.MANUAL_REVIEW: 3,
    Status.ADDITIONAL_INFORMATION_REQUIRED: 4,
    Status.NOT_ELIGIBLE: 5,
    Status.RULES_UNAVAILABLE: 6,
}


def _product_label(product: str) -> str:
    return product.replace("_", " ").title()


class Engine:
    def __init__(self, store: Optional[RuleStore] = None):
        self.store = store or get_store()
        self.gates = GateEvaluator(self.store)

    # ------------------------------------------------------------------ tenure
    def _tenure_bounds(self, product: str, segment: str, lender: str,
                       d: pp.DerivedView) -> tuple[int, int]:
        """(min, max) permitted tenure in months, max clipped by the age-at-maturity cap."""
        pmin = af._resolve_value(self.store, lender, product, segment, "tenure_min_months", pick_min=False) or 12
        pmax = af._resolve_value(self.store, lender, product, segment, "tenure_max_months", pick_min=True) or 60
        mat = af._resolve_value(self.store, lender, product, segment, "age_max_at_maturity", pick_min=True)
        cap = int(pmax)
        if mat is not None:
            cap = pp.max_tenure_by_age(d.age_at_application, mat, int(pmax))
        return int(pmin), max(0, cap)

    def _permitted_requested_tenure(self, app: Applicant, product: str, segment: str,
                                    lender: str, d: pp.DerivedView) -> tuple[int, bool]:
        """The tenure actually usable for the REQUESTED loan, and whether the exact
        requested tenure is supported (never silently rewritten; see defect F)."""
        pmin, cap = self._tenure_bounds(product, segment, lender, d)
        if app.requested_tenure_months:
            want = app.requested_tenure_months
            permitted = max(pmin, min(want, cap))
            return permitted, (permitted == want)
        return max(pmin, cap), True

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
        pmin_t, max_tenure = self._tenure_bounds(product, segment, lender, d)
        permitted_req_tenure, req_tenure_supported = self._permitted_requested_tenure(
            app, product, segment, lender, d)
        if max_tenure < 1 or permitted_req_tenure < 1:
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

        exc_possible, exc_note = af.selective_exception(self.store, lender, product, segment)
        offer.caps = CapBreakdown(
            foir=sizing.caps.get("foir"), take_home=sizing.caps.get("take_home"),
            multiple=sizing.caps.get("multiple"), product=sizing.caps.get("product"),
            calculator=sizing.caps.get("calculator"), binding_cap=sizing.binding_cap,
            selective_exception_possible=exc_possible, selective_exception_note=exc_note,
        )

        # does the max cover the requested AMOUNT?
        requested_amount = app.requested_amount
        amount_supported = requested_amount is None or max_loan >= requested_amount - 1

        from .finance import emi as _emi

        # REQUESTED quote: always the applicant's EXACT requested principal + requested tenure
        # (defect F/G: never rewrite the request). Only populated when a request was made.
        if requested_amount is not None:
            # price at the requested amount if supported, else at the requested amount anyway
            # for the illustrative EMI/rate (the status flags it as not covered).
            price_req_amount = requested_amount if amount_supported else requested_amount
            pricing, req_emi = pr.price_full(
                self.store, lender, product, segment, band,
                price_req_amount, permitted_req_tenure, is_female=is_female,
                bureau_soft_flags=gate.bureau_soft_flags,
                application_date=app.application_date)
            offer.requested = AmountQuote(amount=requested_amount,
                                          tenure_months=app.requested_tenure_months or permitted_req_tenure,
                                          emi=round(_emi(requested_amount, pricing.nominal_rate_pa,
                                                         app.requested_tenure_months or permitted_req_tenure), 2))
        else:
            # no explicit request: price on the max amount at the max tenure
            pricing, _ = pr.price_full(self.store, lender, product, segment, band,
                                       max_loan, max_tenure, is_female=is_female,
                                       bureau_soft_flags=gate.bureau_soft_flags,
                                       application_date=app.application_date)
        offer.pricing = pricing

        # MAX eligible quote at the MAX permitted tenure
        max_emi = round(_emi(max_loan, pricing.nominal_rate_pa, max_tenure), 2)
        offer.max_eligible = AmountQuote(amount=max_loan, tenure_months=max_tenure, emi=max_emi)

        # ALTERNATIVE quote: shown only when the request is not fully supported.
        # amount = min(requested, max_loan); tenure = permitted requested tenure.
        if requested_amount is not None and (not amount_supported or not req_tenure_supported):
            alt_amount = min(requested_amount, max_loan)
            offer.alternative = AmountQuote(
                amount=alt_amount, tenure_months=permitted_req_tenure,
                emi=round(_emi(alt_amount, pricing.nominal_rate_pa, permitted_req_tenure), 2))

        offer.requested_supported = bool(amount_supported)
        offer.requested_tenure_supported = bool(req_tenure_supported)

        fl = af.foir_limit(self.store, lender, product, segment)
        offer.strength_score = st.strength(app, d, lender, fl, max_loan)
        offer.strength_band = st.band(offer.strength_score)
        offer.lowest_confidence = pricing.rate_confidence or Confidence.PUBLISHED
        offer.apr_reliable = pricing.rate_confidence in (Confidence.PUBLISHED, Confidence.PUBLISHED_CONFLICT)

        # status routing (plan2 §4):
        #   PRELIMINARILY_ELIGIBLE          - repriced on bureau signals, estimated rate, or
        #                                     card-outstanding affordability is undetermined
        #   ELIGIBLE_FOR_ALTERNATIVE_TERMS  - passes rules but the exact amount/tenure is not met
        #   ELIGIBLE_FOR_REQUESTED_TERMS    - passes rules and covers the exact request on published pricing
        rate_pub = pricing.rate_confidence in (Confidence.PUBLISHED, Confidence.PUBLISHED_CONFLICT)
        fully_supported = amount_supported and req_tenure_supported
        if (gate.bureau_soft_flags or not rate_pub or not app.card_obligation_known
                or sizing.binding_is_estimated):
            offer.status = Status.PRELIMINARILY_ELIGIBLE
        elif not fully_supported:
            offer.status = Status.ELIGIBLE_FOR_ALTERNATIVE_TERMS
        else:
            offer.status = Status.ELIGIBLE_FOR_REQUESTED_TERMS

        if gate.bureau_soft_flags:
            offer.reasons.append(ReasonCode(
                code="REPRICED", variable="bureau_reject_signal",
                message="terms repriced and amount reduced due to bureau signals",
                rule_status=RuleStatus.ESTIMATED, confidence=Confidence.ESTIMATED,
                next_action="Improve the bureau profile for standard pricing."))
        if not app.card_obligation_known:
            offer.reasons.append(ReasonCode(
                code="CARD_OUTSTANDING_UNKNOWN", variable="card_outstanding",
                message="affordability not fully determined: no published rule for card-outstanding treatment",
                rule_status=RuleStatus.ESTIMATED, confidence=Confidence.ESTIMATED,
                next_action="Provide the monthly repayment obligation on the card balance."))
        if not amount_supported:
            offer.reasons.append(ReasonCode(
                code="AMOUNT_NOT_COVERED", variable="loan_max",
                message="requested amount exceeds the maximum this product supports",
                applicant_value=str(requested_amount), required_value=f"<= {max_loan}",
                rule_status=RuleStatus.DERIVED,
                next_action="Request up to the maximum, or choose a higher-cap lender."))
        if not req_tenure_supported:
            offer.reasons.append(ReasonCode(
                code="TENURE_NOT_SUPPORTED", variable="tenure_max_months",
                message="requested tenure is outside the lender's permitted range",
                applicant_value=str(app.requested_tenure_months),
                required_value=f"{pmin_t}-{max_tenure}",
                rule_status=RuleStatus.PUBLISHED,
                next_action="Choose a tenure within the permitted range."))
        if sizing.binding_is_estimated:
            offer.reasons.append(ReasonCode(
                code="MAX_AMOUNT_ESTIMATED", variable=sizing.binding_cap,
                message="maximum amount rests on an estimated sizing rule (no published cap); treat as indicative",
                rule_status=RuleStatus.ESTIMATED, confidence=Confidence.ESTIMATED,
                next_action="Confirm the lender's published amount cap / income multiple."))
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

        # transparent ranking: covering offers with a RELIABLE APR form the primary ranking;
        # offers whose APR rests on an estimated rate are listed separately as indicative.
        covering = [o for o in eligible if o.status.covers_request]
        pool = covering or eligible
        reliable = [o for o in pool if o.apr_reliable]
        indicative = [o for o in pool if not o.apr_reliable]
        reliable_ranked = sorted(reliable, key=lambda o: (
            o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9,
            o.requested.emi if o.requested.emi is not None else 1e18, o.lender_id))
        indic_ranked = sorted(indicative, key=lambda o: (
            o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9, o.lender_id))

        decision = Decision(
            eligible=bool(eligible),
            offers=offers,
            best_offer=best,
            best_rationale=rationale,
            ranked_lender_ids=[o.lender_id for o in reliable_ranked],
            indicative_lender_ids=[o.lender_id for o in indic_ranked],
            score_method=st.SCORE_METHOD,
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
    """Rank eligible options. The best match must cover the exact requested amount+tenure
    (defect H) and should have a reliable (published) APR; only when nothing qualifies do we
    fall back, and the rationale says so."""
    if not eligible:
        return None, ""
    covering = [o for o in eligible if o.status.covers_request]
    pool = covering or eligible
    reliable = [o for o in pool if o.apr_reliable]
    rank_pool = reliable or pool
    ranked = sorted(rank_pool, key=lambda o: (o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9,
                                              (o.requested.emi if o.requested.emi is not None else 1e18),
                                              o.lender_id))
    best = ranked[0]
    if covering and best in covering:
        note = "covering the exact requested amount and tenure"
    else:
        note = "offering the closest affordable alternative (the request is not fully covered)"
    rel = "" if best.apr_reliable else " (APR indicative — rate estimated)"
    rationale = (f"Lowest APR ({best.pricing.apr_pa}%){rel} among {len(rank_pool)} eligible products "
                 f"{note}; nominal rate {best.pricing.nominal_rate_pa}%.")
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
