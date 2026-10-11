"""Print the conflicts the engine resolves, for human review.

Usage: .venv\\Scripts\\python.exe scripts/show_conflicts.py [lender ...]
"""
import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
only = set(sys.argv[1:])
with (DATA / "conflicts.csv").open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if only and r["lender_id"] not in only:
            continue
        cond = f" [{r['condition'][:30]}]" if r["condition"] else ""
        print(f"{r['lender_id']:<11}{r['product'][:26]:<27}{r['segment']:<9}{r['variable']:<24}{cond}")
        print(f"{'':<11}-> engine uses {r['engine_value']!r} ({r['engine_confidence']}, {r['policy']})")
        print(f"{'':<11}   alternatives: {r['alternatives'][:150]}")
