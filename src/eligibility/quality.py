"""Model-quality summary (§15): a transparent, honest view of the rule base's coverage.

These are NOT lender approval rates and NOT approval-probability predictions. They describe
how much of the engine's rule base is published vs estimated, and how many products can be
priced and sized reliably.
"""
from __future__ import annotations

from collections import Counter

from .rules import RuleStore, get_store


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
    for ir in rows:
        by_conf[ir.rule.confidence.value] += 1

    return {
        "lenders_configured": len(store.lenders()),
        "products_configured": len(products),
        "products_with_published_rules": verified,
        "products_mostly_estimated": mostly_estimated,
        "products_apr_reliable": apr_ready,
        "rules_total": len(rows),
        "rules_by_confidence": dict(by_conf),
        "note": ("Coverage of the published rule base, not lender approval rates. "
                 "The engine screens published criteria and does not predict approval probability."),
    }
