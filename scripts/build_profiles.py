"""Write the 16 sample-profile fixtures (P01-P16) as JSON, from model_report.md section 12.

Ages are converted to a date_of_birth at application_date 2026-01-01. Run once:
  .venv\\Scripts\\python.exe scripts/build_profiles.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

APP = dt.date(2026, 1, 1)
OUT = Path(__file__).resolve().parents[1] / "tests" / "profiles"
OUT.mkdir(parents=True, exist_ok=True)


def dob(age_years: float) -> str:
    return (APP - dt.timedelta(days=int(age_years * 365.25))).isoformat()


PROFILES = {
    "P01": dict(desc="Prime salaried, MNC, metro", employment_type="salaried",
                net_monthly_income=120000, existing_emi_monthly=15000, bureau_score=800,
                total_experience_months=120, current_job_tenure_months=60, employer_category="private_ltd",
                city="Mumbai", requested_amount=800000, requested_tenure_months=48, dob_age=32),
    "P02": dict(desc="Low score 640, recent DPD and enquiries", employment_type="salaried",
                net_monthly_income=80000, existing_emi_monthly=10000, bureau_score=640,
                max_dpd_last_12m=30, enquiries_last_6m=4, total_experience_months=96,
                current_job_tenure_months=36, employer_category="private_ltd", city="Delhi",
                requested_amount=500000, requested_tenure_months=48, dob_age=35),
    "P03": dict(desc="High existing EMI ~55%", employment_type="salaried",
                net_monthly_income=100000, existing_emi_monthly=55000, bureau_score=760,
                total_experience_months=120, current_job_tenure_months=60, employer_category="private_ltd",
                city="Bengaluru", requested_amount=600000, requested_tenure_months=60, dob_age=38),
    "P04": dict(desc="New job 4 months", employment_type="salaried",
                net_monthly_income=90000, bureau_score=770, total_experience_months=36,
                current_job_tenure_months=4, employer_category="private_ltd", city="Pune",
                requested_amount=500000, requested_tenure_months=36, dob_age=27),
    "P05": dict(desc="Fresher 21, 8 months exp, NTC", employment_type="salaried",
                net_monthly_income=45000, bureau_score=None, total_experience_months=8,
                current_job_tenure_months=8, employer_category="private_ltd", city="Pune",
                requested_amount=200000, requested_tenure_months=36, dob_age=21),
    "P06": dict(desc="Age 57, wants 60 months", employment_type="salaried",
                net_monthly_income=150000, existing_emi_monthly=20000, bureau_score=780,
                total_experience_months=360, current_job_tenure_months=120, employer_category="private_ltd",
                city="Chennai", requested_amount=1000000, requested_tenure_months=60, dob_age=57),
    "P07": dict(desc="Self-employed doctor", employment_type="sep", profession="doctor",
                net_monthly_income=200000, business_vintage_months=72, bureau_score=790,
                itr_years_filed=3, itr_income_y1=2400000, itr_income_y2=2200000,
                total_experience_months=180, city="Mumbai",
                requested_amount=1500000, requested_tenure_months=60, dob_age=40),
    "P08": dict(desc="Business owner, 2yr vintage, 1 ITR", employment_type="seb",
                net_monthly_income=120000, business_vintage_months=24, bureau_score=720,
                itr_years_filed=1, itr_income_y1=1440000, total_experience_months=120,
                city="Ahmedabad", requested_amount=1000000, requested_tenure_months=48, dob_age=36),
    "P09": dict(desc="New-to-credit, no score", employment_type="salaried",
                net_monthly_income=70000, bureau_score=None, total_experience_months=60,
                current_job_tenure_months=36, employer_category="private_ltd", city="Hyderabad",
                requested_amount=400000, requested_tenure_months=36, dob_age=29),
    "P10": dict(desc="DPD 60 in 12m, score 720", employment_type="salaried",
                net_monthly_income=95000, bureau_score=720, max_dpd_last_12m=60,
                total_experience_months=96, current_job_tenure_months=48, employer_category="private_ltd",
                city="Delhi", requested_amount=600000, requested_tenure_months=48, dob_age=34),
    "P11": dict(desc="9 enquiries in 6 months", employment_type="salaried",
                net_monthly_income=110000, bureau_score=710, enquiries_last_6m=9,
                total_experience_months=108, current_job_tenure_months=60, employer_category="private_ltd",
                city="Bengaluru", requested_amount=700000, requested_tenure_months=48, dob_age=31),
    "P12": dict(desc="Tier-3 city, low income", employment_type="salaried",
                net_monthly_income=22000, bureau_score=730, total_experience_months=60,
                current_job_tenure_months=36, employer_category="private_ltd", city="Rourkela",
                requested_amount=150000, requested_tenure_months=36, dob_age=30),
    "P13": dict(desc="High earner wants 50L", employment_type="salaried",
                net_monthly_income=300000, bureau_score=810, total_experience_months=180,
                current_job_tenure_months=96, employer_category="private_ltd", city="Mumbai",
                requested_amount=5000000, requested_tenure_months=60, dob_age=42),
    "P14": dict(desc="Govt employee, SBI salary account", employment_type="salaried",
                net_monthly_income=85000, bureau_score=760, total_experience_months=240,
                current_job_tenure_months=120, employer_category="govt", city="Lucknow",
                salary_account_with_lender="sbi", requested_amount=1200000,
                requested_tenure_months=60, dob_age=45),
    "P15": dict(desc="Exactly at thresholds", employment_type="salaried",
                net_monthly_income=25000, bureau_score=700, total_experience_months=12,
                current_job_tenure_months=12, employer_category="private_ltd", city="Jaipur",
                requested_amount=300000, requested_tenure_months=36, dob_age=21),
    "P16": dict(desc="Settled loan 18m ago", employment_type="salaried",
                net_monthly_income=90000, bureau_score=680, writeoff_or_settled_24m=True,
                total_experience_months=120, current_job_tenure_months=60, employer_category="private_ltd",
                city="Delhi", requested_amount=500000, requested_tenure_months=48, dob_age=39),
}


def main() -> None:
    for pid, p in PROFILES.items():
        age = p.pop("dob_age")
        desc = p.pop("desc")
        rec = {"profile_id": pid, "description": desc, "date_of_birth": dob(age),
               "application_date": APP.isoformat(), **p}
        (OUT / f"{pid}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"wrote {len(PROFILES)} profiles to {OUT}")


if __name__ == "__main__":
    main()
