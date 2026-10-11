"""Command-line interface: evaluate an applicant JSON against all 20 lenders.

Usage:
  python -m eligibility evaluate path/to/applicant.json [--json] [--fixes]
  python -m eligibility evaluate -            # read JSON from stdin
  python -m eligibility profiles             # list bundled sample profiles

Output is a human table by default, or machine JSON with --json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .counterfactual import suggest
from .engine import Engine
from .schema import Applicant, Status


def _load(src: str) -> dict:
    if src == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(src).read_text(encoding="utf-8"))


def _applicant_from(rec: dict) -> Applicant:
    rec = dict(rec)
    rec.pop("profile_id", None)
    rec.pop("description", None)
    return Applicant(**rec)


def _print_table(engine: Engine, app: Applicant, with_fixes: bool) -> None:
    d = engine.run(app)
    n = sum(1 for o in d.offers if o.status.is_offer)
    print(f"Applicant age {d.applicant_age} | eligible: {'YES' if d.eligible else 'NO'} | {n}/20 products matched")
    if d.best_offer:
        b = d.best_offer
        me, rq = b.max_eligible, b.requested
        print(f"\nBEST: {b.lender_id.upper()} [{b.product_label}] {b.status.value}")
        print(f"  max eligible: Rs{me.amount:,.0f} over {me.tenure_months}m  EMI Rs{me.emi:,.0f}/mo")
        if rq.amount:
            print(f"  requested:    Rs{rq.amount:,.0f} over {rq.tenure_months}m  EMI Rs{rq.emi:,.0f}/mo"
                  f"  ({'covered' if b.requested_supported else 'reduced'})")
        p = b.pricing
        print(f"  rate {p.nominal_rate_pa}%  APR {p.apr_pa}%  fee Rs{p.processing_fee:,.0f} + GST Rs{p.gst_on_fee:,.0f}"
              f"  net Rs{p.net_disbursement:,.0f}  strength {b.strength_score}/100")
        if b.rationale:
            print(f"  why: {b.rationale}")

    print(f"\n{'lender':<12}{'status':<28}{'max eligible':>14}{'req EMI':>11}{'rate':>7}{'APR':>8}")
    print("-" * 80)
    offers = sorted(d.offers, key=lambda o: (not o.status.is_offer,
                                             o.pricing.apr_pa if o.pricing.apr_pa is not None else 1e9,
                                             o.lender_id))
    for o in offers:
        if o.status.is_offer:
            print(f"{o.lender_id:<12}{o.status.value:<28}{o.max_eligible.amount:>14,.0f}"
                  f"{(o.requested.emi or 0):>11,.0f}{o.pricing.nominal_rate_pa:>6}%{o.pricing.apr_pa:>7}%")
        else:
            top = o.reasons[0].code if o.reasons else o.status.value
            print(f"{o.lender_id:<12}{o.status.value:<28}{'-':>14}{'-':>11}{'-':>7}{top:>8}")

    if not d.eligible and d.top_blocking_reasons:
        print("\nTop blocking reasons:", ", ".join(r.code for r in d.top_blocking_reasons))

    if with_fixes:
        print("\nSuggested next steps for non-eligible lenders:")
        for o in d.offers:
            if not o.status.is_offer:
                fixes = suggest(engine, app, o)
                if fixes:
                    joined = "; ".join(f.description for f in fixes)
                    print(f"  {o.lender_id}: {joined}")


def _decision_json(engine: Engine, app: Applicant, with_fixes: bool) -> dict:
    d = engine.run(app)
    out = d.model_dump(mode="json")
    if with_fixes:
        for o, raw in zip(d.offers, out["offers"]):
            if not o.status.is_offer:
                raw["fixes"] = [f.model_dump() for f in suggest(engine, app, o)]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eligibility", description="Personal-loan eligibility engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("evaluate", help="evaluate an applicant JSON file (or - for stdin)")
    ev.add_argument("source")
    ev.add_argument("--json", action="store_true", help="emit machine JSON")
    ev.add_argument("--fixes", action="store_true", help="include counterfactual fixes")

    sub.add_parser("profiles", help="list bundled sample profiles")
    sub.add_parser("summary", help="print the model-quality summary (rule coverage)")

    args = parser.parse_args(argv)
    engine = Engine()

    if args.cmd == "profiles":
        prof_dir = Path(__file__).resolve().parents[2] / "tests" / "profiles"
        for pf in sorted(prof_dir.glob("P*.json")):
            rec = json.loads(pf.read_text(encoding="utf-8"))
            print(f"{rec.get('profile_id', pf.stem)}: {rec.get('description', '')}")
        return 0

    if args.cmd == "summary":
        from .quality import model_summary
        print(json.dumps(model_summary(engine.store), indent=2))
        return 0

    if args.cmd == "evaluate":
        app = _applicant_from(_load(args.source))
        if args.json:
            print(json.dumps(_decision_json(engine, app, args.fixes), indent=2))
        else:
            _print_table(engine, app, args.fixes)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
