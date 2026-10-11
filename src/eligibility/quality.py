"""Model-quality summary (§15): a transparent, honest view of the rule base's coverage.

These are NOT lender approval rates and NOT approval-probability predictions. They describe
how much of the engine's rule base is published vs estimated, and how many products can be
priced and sized reliably.
"""
from __future__ import annotations

from collections import Counter

from .rules import RuleStore, get_store

# the internal CSV confidence vocabulary -> plan2's rule-confidence taxonomy (§8)
CONFIDENCE_LABELS = {
    "published": "VERIFIED_PUBLISHED",
    "published_conflict": "CONFLICT_REQUIRES_REVIEW",
    "derived": "INFERRED",
    "estimated": "ESTIMATED",
    "estimated_superseded": "ESTIMATED",
}

# variables that materially decide an outcome; a product needs these for a "complete" rating
KEY_GATE_VARS = {"age_min", "income_min_monthly", "score_min"}
KEY_SIZE_VARS = {"loan_max", "foir_max", "income_multiple_max", "take_home_floor"}
KEY_PRICE_VARS = {"rate_min_pa", "rate_max_pa", "rate_grid"}
KEY_FEE_VARS = {"processing_fee_pct", "processing_fee_flat_inr"}

_FIRM = {"published", "published_conflict"}


def label_for(confidence: str) -> str:
    return CONFIDENCE_LABELS.get(confidence, "UNKNOWN")


def product_completeness(store: RuleStore | None = None) -> list[dict]:
    """Per-product completeness: which material rule groups are published vs estimated/absent.

    rating:
      complete     - every material group (gate, sizing, pricing, fee) has a published source
      partial      - some material groups are published, others estimated/inferred
      insufficient - no published pricing+sizing, i.e. an unreliable product
    """
    store = store or get_store()
    groups = {"gate": KEY_GATE_VARS, "sizing": KEY_SIZE_VARS,
              "pricing": KEY_PRICE_VARS, "fee": KEY_FEE_VARS}

    # (lender, product) -> variable -> set of confidences seen
    per: dict[tuple[str, str], dict[str, set]] = {}
    for ir in store.all():
        key = (ir.rule.lender_id, ir.rule.product)
        per.setdefault(key, {}).setdefault(ir.variable, set()).add(ir.rule.confidence.value)

    out = []
    for (lender, product), vars_ in sorted(per.items()):
        status = {}
        for gname, gvars in groups.items():
            present = gvars & set(vars_)
            if not present:
                status[gname] = "absent"
            elif any(_FIRM & vars_[v] for v in present):
                status[gname] = "published"
            else:
                status[gname] = "estimated"
        published = sum(1 for v in status.values() if v == "published")
        has_price = status["pricing"] == "published"
        has_size = status["sizing"] == "published"
        if published == 4:
            rating = "complete"
        elif has_price and has_size:
            rating = "partial"
        elif published >= 1:
            rating = "partial"
        else:
            rating = "insufficient"
        out.append({"lender_id": lender, "product": product, "rating": rating, "groups": status})
    return out


def model_summary(store: RuleStore | None = None) -> dict:
    store = store or get_store()
    rows = store.all()

    products: set[tuple[str, str]] = set()
    product_conf: dict[tuple[str, str], Counter] = {}
    rate_products: set[tuple[str, str]] = set()
    fee_products: set[tuple[str, str]] = set()

    for ir in rows:
        key = (ir.rule.lender_id, ir.rule.product)
        products.add(key)
        product_conf.setdefault(key, Counter())[ir.rule.confidence.value] += 1
        if ir.variable in ("rate_min_pa", "rate_max_pa", "rate_grid"):
            rate_products.add(key)
        if ir.variable in ("processing_fee_pct", "processing_fee_flat_inr"):
            fee_products.add(key)

    verified = sum(1 for k in products
                   if product_conf[k].get("published", 0) + product_conf[k].get("published_conflict", 0) > 0)
    mostly_estimated = sum(1 for k in products
                           if product_conf[k].get("estimated", 0) >
                           product_conf[k].get("published", 0) + product_conf[k].get("published_conflict", 0))
    # a product can be reliably APR-priced if it has both a rate and a fee source
    apr_ready = len(rate_products & fee_products)

    by_conf: Counter = Counter()
    by_label: Counter = Counter()
    for ir in rows:
        by_conf[ir.rule.confidence.value] += 1
        by_label[label_for(ir.rule.confidence.value)] += 1

    completeness = product_completeness(store)
    comp_counts = Counter(c["rating"] for c in completeness)

    return {
        "lenders_configured": len(store.lenders()),
        "products_configured": len(products),
        "products_with_published_rules": verified,
        "products_mostly_estimated": mostly_estimated,
        "products_apr_reliable": apr_ready,
        "products_complete": comp_counts.get("complete", 0),
        "products_partial": comp_counts.get("partial", 0),
        "products_insufficient": comp_counts.get("insufficient", 0),
        "rules_total": len(rows),
        "rules_by_confidence": dict(by_conf),
        "rules_by_label": dict(by_label),
        "note": ("Coverage of the published rule base, not lender approval rates. "
                 "The engine screens published criteria and does not predict approval probability."),
    }
