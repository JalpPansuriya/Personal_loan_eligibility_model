"""Print a quick view of calibration probe results.

Usage: .venv\\Scripts\\python.exe scripts/show_probes.py [lender ...]
"""
import csv
import sys
from pathlib import Path

CAL = Path(__file__).resolve().parents[1] / "data" / "calibration"
for f in sorted(CAL.glob("probes_*.csv")):
    lender = f.stem.split("_")[1]
    if sys.argv[1:] and lender not in sys.argv[1:]:
        continue
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    ok = [r for r in rows if r["max_loan"]]
    print(f"== {f.name}: {len(ok)}/{len(rows)} with value")
    for r in rows:
        print(f"  emp={r['employer'][:16]:<17} inc={r['income']:>7} emi={r['existing_emi']:>6} "
              f"ten={r['tenure_years']:<2} hold={r['holdout']} -> {r['max_loan'] or '-':>10}  {r['raw'][:60]}")
