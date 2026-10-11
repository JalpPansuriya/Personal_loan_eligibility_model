"""Fit hidden sizing rules from calculator probes, score them on held-out points.

Only probes with holdout=0 are used for fitting; holdout=1 points are used only for scoring.

Models:
  kotak:  max_loan = floor_10k( m * (income - existing_emi) ), capped at product max
          (an income multiple applied to income net of obligations)
  icici:  max_loan = min(cap, floor_10k( A * (f * income - existing_emi) ))
          (FOIR f, then EMI capacity capitalised by annuity factor A)
          A is converted to an implied annual rate at 60 and 84 months.

Outputs:
  data/calibration/fit_report.csv     per lender: params, train/holdout MAPE, n
  data/calibration/derived_rules.csv  rule rows (confidence=derived) merged by build_rule_tables.py
Usage: .venv\\Scripts\\python.exe scripts/fit_calibration.py
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "data" / "calibration"
TODAY = "2026-10-10"


def load(lender: str) -> list[dict]:
    rows = []
    for f in sorted(CAL.glob(f"probes_{lender}*.csv")):
        for r in csv.DictReader(f.open(encoding="utf-8")):
            if r["max_loan"]:
                rows.append({"income": float(r["income"]), "emi": float(r["existing_emi"]),
                             "tenure": r["tenure_years"], "employer": r["employer"],
                             "y": float(r["max_loan"]), "holdout": r["holdout"] == "1", "url": r["url"]})
    return rows


def floor10k(x: float) -> float:
    return math.floor(max(x, 0) / 10000) * 10000


def mape(pred: list[float], y: list[float]) -> float:
    return float(np.mean([abs(p - t) / t for p, t in zip(pred, y) if t > 0])) * 100 if y else float("nan")


def annuity_rate(factor: float, n: int) -> float:
    """Annual nominal rate r such that PV of 1/month for n months at r/12 equals factor."""
    f = lambda m: (1 - (1 + m) ** -n) / m - factor
    return brentq(f, 1e-6, 0.1) * 12 * 100


def fit_kotak(rows):
    tr = [r for r in rows if not r["holdout"]]
    x = np.array([r["income"] - r["emi"] for r in tr]); y = np.array([r["y"] for r in tr])
    m = float((x @ y) / (x @ x))
    m_round = round(m)
    pred = lambda r: floor10k(m_round * (r["income"] - r["emi"]))
    tenure_effect = max(abs(a["y"] - b["y"]) for a in rows for b in rows
                        if a["income"] == b["income"] and a["emi"] == b["emi"] and a["tenure"] != b["tenure"])
    return {"m_fit": m, "multiple_net_of_obligations": m_round, "tenure_effect_inr": tenure_effect}, pred


def fit_icici(rows, cap=5000000):
    tr = [r for r in rows if not r["holdout"] and r["y"] < cap]
    X = np.array([[r["income"], -r["emi"]] for r in tr]); y = np.array([r["y"] for r in tr])
    (a, b), *_ = np.linalg.lstsq(X, y, rcond=None)
    A, f = float(b), float(a / b)
    pred = lambda r: min(cap, floor10k(A * (f * r["income"] - r["emi"])))
    # employer sensitivity: same income/EMI probed under different employers
    by_key: dict[tuple, set] = {}
    for r in rows:
        by_key.setdefault((r["income"], r["emi"]), set()).add((r["employer"], r["y"]))
    multi = [v for v in by_key.values() if len({e for e, _ in v}) > 1]
    employer_diff = max((max(y for _, y in v) - min(y for _, y in v)) for v in multi) if multi else float("nan")
    employers = sorted({r["employer"] for r in rows})
    return {"annuity_factor": A, "foir": f, "cap": cap,
            "implied_rate_60m": annuity_rate(A, 60), "implied_rate_84m": annuity_rate(A, 84),
            "employers_probed": " + ".join(employers), "max_diff_across_employers_inr": employer_diff}, pred


DERIVED_HEADER = ["rule_id", "lender_id", "product", "segment", "variable", "operator", "value", "unit", "effect",
                  "condition", "source_url", "source_file", "accessed_date", "confidence", "estimation_method",
                  "quote", "notes"]


def main() -> None:
    report, derived = [], []
    for lender, fit, product in (("kotak", fit_kotak, "kotak_personal_loan"),
                                 ("icici", fit_icici, "icici_personal_loan")):
        rows = load(lender)
        if not rows:
            print(f"{lender}: no probe data"); continue
        params, pred = fit(rows)
        tr = [r for r in rows if not r["holdout"]]; ho = [r for r in rows if r["holdout"]]
        tr_mape = mape([pred(r) for r in tr], [r["y"] for r in tr])
        ho_mape = mape([pred(r) for r in ho], [r["y"] for r in ho])
        ho_exact = sum(pred(r) == r["y"] for r in ho)
        report.append({"lender": lender, "n_train": len(tr), "n_holdout": len(ho),
                       "train_mape_pct": round(tr_mape, 3), "holdout_mape_pct": round(ho_mape, 3),
                       "holdout_exact": f"{ho_exact}/{len(ho)}",
                       "params": "; ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in params.items()),
                       "probed_url": rows[0]["url"]})
        method = (f"fitted to {len(tr)} calculator probes ({rows[0]['url']}, {TODAY}); "
                  f"held-out MAPE {ho_mape:.2f}% on {len(ho)} points ({ho_exact} exact)")
        src_files = " + ".join(sorted({f.name for f in CAL.glob(f"probes_{lender}*.csv")}))
        base = {"lender_id": lender, "product": product, "segment": "salaried", "condition": "",
                "source_url": rows[0]["url"], "source_file": src_files,
                "accessed_date": TODAY, "confidence": "derived", "estimation_method": method, "quote": ""}
        if lender == "kotak":
            derived += [
                {**base, "rule_id": "kotak-c01", "variable": "income_multiple_max", "operator": "formula",
                 "value": str(params["multiple_net_of_obligations"]), "unit": "x_income", "effect": "multiple",
                 "notes": "multiple applied to (net income - existing obligations); calculator result independent "
                          f"of tenure (max diff {params['tenure_effect_inr']:.0f} INR); result floored to 10,000"},
                {**base, "rule_id": "kotak-c02", "variable": "foir_max", "operator": "info", "value": "none_observed",
                 "unit": "text", "effect": "info",
                 "notes": "calculator sizes on net-of-obligation multiple, no separate FOIR cap observed"},
            ]
        else:
            derived += [
                {**base, "rule_id": "icici-c01", "variable": "foir_max", "operator": "<=",
                 "value": f"{params['foir'] * 100:.1f}", "unit": "pct", "effect": "foir",
                 "notes": f"loan = annuity_factor x (FOIR x income - existing EMI); annuity_factor={params['annuity_factor']:.2f}; "
                          f"employers probed: {params['employers_probed']}; max difference across employers "
                          f"{params['max_diff_across_employers_inr']:.0f} INR"},
                {**base, "rule_id": "icici-c02", "variable": "rate_min_pa", "operator": "info",
                 "value": f"{params['implied_rate_60m']:.2f}", "unit": "pct_pa", "effect": "info",
                 "notes": f"rate implied by annuity factor if calculator assumes 60 months "
                          f"({params['implied_rate_84m']:.2f}% if 84 months); sizing assumption, not a quote"},
                {**base, "rule_id": "icici-c03", "variable": "loan_max", "operator": "<=", "value": str(params["cap"]),
                 "unit": "inr", "effect": "amount_cap", "notes": "calculator output saturates at 50,00,000"},
            ]
        print(f"{lender}: {report[-1]['params']}\n   train MAPE {tr_mape:.2f}%  holdout MAPE {ho_mape:.2f}%  "
              f"exact {ho_exact}/{len(ho)}")
    with (CAL / "fit_report.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0])); w.writeheader(); w.writerows(report)
    with (CAL / "derived_rules.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DERIVED_HEADER); w.writeheader(); w.writerows(derived)


if __name__ == "__main__":
    main()
