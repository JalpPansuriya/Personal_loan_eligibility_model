"""Build lookup tables the engine needs.

  data/lookups/city_tier.csv      city -> HRA class (X/Y/Z) -> engine tier (1/2/3), aliases, Axis serviceability
  data/lookups/rate_grids/{lender}.csv  rate-grid cells pulled from data/lender_rules_long.csv
  data/lookups/profession_allowlist.csv  lender x product x profession (from profession_allowed rules)
  data/lookups/employer_category.csv     lender x product x allowed employer categories

Sources for city tiers: Ministry of Finance, Dept of Expenditure O.M. No. 2/5/2017-E.II(B) dated 07-07-2017
(HRA classification, 2011 Census), as reproduced in EPFO circular HRD_7CPC_HRA_2313 (archived):
https://web.archive.org/web/2020/https://www.epfindia.gov.in/site_docs/PDFs/Circulars/Y2017-2018/HRD_7CPC_HRA_2313.pdf
Para 6 of the O.M. pays Faridabad, Ghaziabad, NOIDA and Gurgaon at Delhi (X) rates; we map them to X.
Axis tiers: https://www.axis.bank.in/loans/personal-loan (snapshot axis__www_axis_bank_in_loans_personal_loan__*.md)
Usage: .venv\\Scripts\\python.exe scripts/build_lookups.py
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOOK = DATA / "lookups"
HRA_SRC = ("MoF DoE O.M. 2/5/2017-E.II(B) 07-07-2017 (HRA, Census 2011), via EPFO circular "
           "https://web.archive.org/web/2020/https://www.epfindia.gov.in/site_docs/PDFs/Circulars/Y2017-2018/HRD_7CPC_HRA_2313.pdf")

X_CITIES = ["Hyderabad", "Delhi", "Ahmedabad", "Bengaluru", "Mumbai", "Pune", "Chennai", "Kolkata",
            # para 6: paid at Delhi (X) rates
            "Faridabad", "Ghaziabad", "Noida", "Gurgaon"]
Y_CITIES = [
    "Vijayawada", "Warangal", "Visakhapatnam", "Guntur", "Nellore", "Guwahati", "Patna", "Chandigarh",
    "Durg-Bhilai Nagar", "Raipur", "Rajkot", "Jamnagar", "Bhavnagar", "Vadodara", "Surat", "Srinagar", "Jammu",
    "Jamshedpur", "Dhanbad", "Ranchi", "Bokaro Steel City", "Belgaum", "Hubli-Dharwad", "Mangalore", "Mysore",
    "Gulbarga", "Kozhikode", "Kochi", "Thiruvananthapuram", "Thrissur", "Malappuram", "Kannur", "Kollam",
    "Gwalior", "Indore", "Bhopal", "Jabalpur", "Ujjain", "Amravati", "Nagpur", "Aurangabad", "Nashik", "Bhiwandi",
    "Solapur", "Kolhapur", "Vasai-Virar", "Malegaon", "Nanded", "Sangli", "Cuttack", "Bhubaneswar", "Rourkela",
    "Puducherry", "Amritsar", "Jalandhar", "Ludhiana", "Bikaner", "Jaipur", "Jodhpur", "Kota", "Ajmer", "Salem",
    "Tiruppur", "Coimbatore", "Tiruchirappalli", "Madurai", "Erode", "Moradabad", "Meerut", "Aligarh", "Agra",
    "Bareilly", "Lucknow", "Kanpur", "Prayagraj", "Gorakhpur", "Varanasi", "Saharanpur", "Firozabad", "Jhansi",
    "Dehradun", "Asansol", "Siliguri", "Durgapur",
    # para 6: paid at Y rates
    "Shillong", "Goa", "Port Blair", "Panchkula", "Mohali",
]
ALIASES = {  # alias -> canonical
    "bangalore": "Bengaluru", "bengalore": "Bengaluru", "bombay": "Mumbai", "greater mumbai": "Mumbai",
    "navi mumbai": "Mumbai", "thane": "Mumbai", "new delhi": "Delhi", "ahmadabad": "Ahmedabad", "madras": "Chennai",
    "calcutta": "Kolkata", "gurugram": "Gurgaon", "greater noida": "Noida", "vizag": "Visakhapatnam",
    "vishakhapatnam": "Visakhapatnam", "vishakapatnam": "Visakhapatnam", "vijaywada": "Vijayawada",
    "trivandrum": "Thiruvananthapuram", "thiruvanathapuram": "Thiruvananthapuram", "calicut": "Kozhikode",
    "cochin": "Kochi", "ernakulam": "Kochi", "mysuru": "Mysore", "mangaluru": "Mangalore", "belagavi": "Belgaum",
    "hubli": "Hubli-Dharwad", "dharwad": "Hubli-Dharwad", "kalaburagi": "Gulbarga", "pondicherry": "Puducherry",
    "allahabad": "Prayagraj", "trichy": "Tiruchirappalli", "bhubaneshwar": "Bhubaneswar", "raurkela": "Rourkela",
    "bhilai": "Durg-Bhilai Nagar", "durg": "Durg-Bhilai Nagar", "bokaro": "Bokaro Steel City",
    "sas nagar": "Mohali", "s.a.s. nagar": "Mohali", "nanded-waghala": "Nanded", "vasai": "Vasai-Virar",
    "virar": "Vasai-Virar", "panaji": "Goa", "margao": "Goa", "chhatrapati sambhajinagar": "Aurangabad",
    "secunderabad": "Hyderabad", "cyberabad": "Hyderabad",
}
TIER_OF_CLASS = {"X": 1, "Y": 2, "Z": 3}


def norm_city(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    return ALIASES.get(s, s.title() if s else s)


def axis_cities() -> dict[str, int]:
    """Parse Axis' published 4-tier serviceable city list from its rule rows."""
    out: dict[str, int] = {}
    with (DATA / "lender_rules_long.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["lender_id"] == "axis" and r["variable"] == "city_serviced":
                m = re.search(r"tier\s*==\s*(\d)", r["condition"])
                if not m:
                    continue
                for c in r["value"].split("|"):
                    if c.strip():
                        out[norm_city(c)] = int(m.group(1))
    return out


def build_city_tier() -> int:
    axis = axis_cities()
    rows: dict[str, dict] = {}
    for cls, cities in (("X", X_CITIES), ("Y", Y_CITIES)):
        for c in cities:
            rows[c] = {"city": c, "hra_class": cls, "engine_tier": TIER_OF_CLASS[cls], "source": HRA_SRC}
    for c in axis:  # Axis-listed cities not in X/Y are Z (tier 3) under HRA
        rows.setdefault(c, {"city": c, "hra_class": "Z", "engine_tier": 3,
                            "source": "not in HRA X/Y annexure -> Z (O.M. note: remaining cities are Z)"})
    for r in rows.values():
        r["axis_serviced"] = str(r["city"] in axis).lower()
        r["axis_tier"] = axis.get(r["city"], "")
        r["aliases"] = "|".join(sorted(a for a, canon in ALIASES.items() if canon == r["city"]))
    with (LOOK / "city_tier.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["city", "hra_class", "engine_tier", "axis_serviced", "axis_tier",
                                           "aliases", "source"])
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["engine_tier"], r["city"])))
    missing_axis = [c for c in axis if c not in rows]
    if missing_axis:
        print("WARN axis cities not mapped:", missing_axis)
    return len(rows)


def build_from_rules() -> tuple[int, int, int]:
    with (DATA / "lender_rules_long.csv").open(encoding="utf-8") as fh:
        rules = list(csv.DictReader(fh))
    grid_dir = LOOK / "rate_grids"
    grid_dir.mkdir(parents=True, exist_ok=True)
    for f in grid_dir.glob("*.csv"):
        f.unlink()
    grids: dict[str, list[dict]] = {}
    prof, emp = [], []
    for r in rules:
        if r["variable"] == "rate_grid":
            grids.setdefault(r["lender_id"], []).append(r)
        elif r["variable"] == "profession_allowed":
            for p in r["value"].split("|"):
                if p.strip():
                    prof.append({"lender_id": r["lender_id"], "product": r["product"], "segment": r["segment"],
                                 "profession": p.strip(), "confidence": r["confidence"], "rule_id": r["rule_id"],
                                 "source_url": r["source_url"]})
        elif r["variable"] == "employer_category_allowed":
            for e in r["value"].split("|"):
                if e.strip():
                    emp.append({"lender_id": r["lender_id"], "product": r["product"], "segment": r["segment"],
                                "employer_category": e.strip(), "condition": r["condition"],
                                "confidence": r["confidence"], "rule_id": r["rule_id"], "source_url": r["source_url"]})
    fields = ["rule_id", "product", "segment", "value", "condition", "confidence", "source_url", "quote"]
    for lender, rows in grids.items():
        with (grid_dir / f"{lender}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    for name, rows, fields2 in (("profession_allowlist.csv", prof, list(prof[0]) if prof else []),
                                ("employer_category.csv", emp, list(emp[0]) if emp else [])):
        with (LOOK / name).open("w", encoding="utf-8", newline="") as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=fields2)
                w.writeheader()
                w.writerows(rows)
    return sum(len(v) for v in grids.values()), len(prof), len(emp)


def main() -> None:
    LOOK.mkdir(parents=True, exist_ok=True)
    n_city = build_city_tier()
    n_grid, n_prof, n_emp = build_from_rules()
    print(f"city_tier.csv: {n_city} cities")
    print(f"rate_grids/: {n_grid} cells")
    print(f"profession_allowlist.csv: {n_prof} rows; employer_category.csv: {n_emp} rows")


if __name__ == "__main__":
    main()
