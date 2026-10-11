"""Check that the snapshots actually contain the key facts the earlier web research reported.

A `MISS` means the fact is not in our saved snapshot. Such a value may only be
used as `estimated` (or after re-capture), never as `published`.
Usage: .venv\\Scripts\\python.exe scripts/check_snapshot_coverage.py
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "data" / "sources"

# lender -> list of (fact label, regex) expected somewhere in that lender's snapshots
EXPECT: dict[str, list[tuple[str, str]]] = {
    "sbi": [("EMI/NMI 65%", r"65\s*%"), ("30x NMI", r"30[- ]times"), ("CIBIL 650", r"\b650\b"), ("CIBIL 670", r"\b670\b"),
            ("NTC eligible", r"New[- ]to[- ]Credit"), ("salary account mandatory", r"[Ss]alary [Aa]ccount")],
    "hdfc": [("CIBIL 720", r"\b720\b"), ("25,000 income", r"25,000"), ("6,500 fee", r"6,500")],
    "icici": [("30,000 income", r"30,000"), ("age 58", r"\b58\b"), ("SE age 23", r"23 years"), ("SE maturity 65", r"\b65\b"),
              ("2 years business", r"2 years in the current business")],
    "axis": [("tier city list", r"Coimbatore"), ("15,000 income", r"15,000"), ("maturity 60", r"60 years")],
    "kotak": [("685 score", r"\b685\b"), ("30,000 income", r"30,000"), ("1 crore", r"1 [Cc]rore")],
    "bob": [("75% GMI", r"75\s*%\s*of\s*GMI"), ("20 lakh max", r"20\.00 [Ll]akh"), ("10.15 rate", r"10\.15")],
    "pnb": [("24x salary", r"24 times"), ("20 lakh", r"20\.00 [Ll]akh"), ("72 EMIs", r"\b72\b"), ("SE 750", r"\b750\b")],
    "canara": [("take-home 25%", r"25%\s*or\s*Rs\.?\s*10,000"), ("25 months gross", r"25 months"), ("0.50% fee", r"0\.50%")],
    "union": [("75 years", r"75 years"), ("5 lakh first-time", r"5\.00 lakh"), ("12 lakh professional", r"12\.00 [Ll]akh"),
              ("24 months customer", r"24 months"), ("CA/CS list", r"Chartered Accountant")],
    "indusind": [("730 score", r"\b730\b"), ("4.8 lakh SE", r"4\.8 lakh"), ("25,000 income", r"25,?000")],
    "idfc": [("710 score", r"\b710\b"), ("760 SE", r"\b760\b"), ("10,000 income", r"10,000")],
    "yes": [("700 score", r"\b700\b"), ("25,000 income", r"25,000"), ("72 months", r"\b72\b")],
    "bajaj": [("650 score", r"\b650\b"), ("55 lakh", r"55 lakh"), ("4.13% fee", r"4\.13"), ("settlement reject", r"[Ss]ettlement")],
    "tata": [("725 score", r"\b725\b"), ("FOIR 40-50", r"40% to 50%|40-50%"), ("multiplier 9-18", r"9 to 18")],
    "abcl": [("city grid 18K", r"18K|18,000"), ("700 score", r"\b700\b"), ("28% cap", r"28(\.0)?\s*%")],
    "lnt": [("tier 15,000", r"15,000"), ("700 score", r"\b700\b"), ("10.50-24", r"10\.50")],
    "poonawalla": [("25,000 take-home", r"25,000"), ("700 ideal", r"\b700\b"), ("4% fee", r"4%")],
    "navi": [("3L household", r"3,00,000"), ("29.96", r"29\.96"), ("84 months", r"84 months")],
    "kreditbee": [("10,000 income", r"10,000"), ("NTC welcome", r"[Nn]ew[- ]to[- ]credit|new customers"), ("4.7% fee", r"4\.7")],
    "moneyview": [("650 score", r"\b650\b"), ("21-57 age", r"57"), ("cash salary excluded", r"cash"), ("APR 17-45", r"17\s*%?\s*-\s*45")],
}


def main() -> None:
    miss_total = 0
    for lender, facts in EXPECT.items():
        files = list(SRC.glob(f"{lender}__*.md")) + list(SRC.glob(f"{lender}__*.txt"))
        blob = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
        for label, rx in facts:
            ok = re.search(rx, blob) is not None
            miss_total += not ok
            print(f"{'ok  ' if ok else 'MISS'} {lender:<11} {label}")
    print(f"\n{miss_total} facts missing from snapshots")


if __name__ == "__main__":
    main()
