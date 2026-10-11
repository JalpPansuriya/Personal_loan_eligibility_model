"""Synthetic population + sensitivity analysis (insights, never training).

* population(n, seed): a deterministic synthetic applicant sample using public-ish
  marginal assumptions. Used only to compute approval statistics and the sensitivity of
  estimated rules; it is never fed back as training data.
* sensitivity(): swing every estimated/conflict rule to its alternative value and report
  how many decisions flip (the honest "how much do our estimates matter" number).
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from .engine import Engine
from .schema import Applicant, EmploymentType, Status

APP_DATE = dt.date(2026, 1, 1)


def _dob(age: float) -> dt.date:
    return APP_DATE - dt.timedelta(days=int(age * 365.25))


def population(n: int = 10_000, seed: int = 42) -> list[Applicant]:
    rng = random.Random(seed)
    out: list[Applicant] = []
    for _ in range(n):
        emp = rng.choices(["salaried", "sep", "seb"], weights=[0.7, 0.12, 0.18])[0]
        age = rng.triangular(22, 58, 32)
        income = int(rng.lognormvariate(10.9, 0.5))          # ~ 25k median, long tail
        income = max(12_000, min(income, 2_000_000))
        has_score = rng.random() > 0.12
        score = rng.choices([820, 775, 725, 675, 630], weights=[0.2, 0.3, 0.25, 0.15, 0.1])[0] if has_score else None
        emi = int(income * rng.betavariate(1.5, 6))
        kw = dict(
            employment_type=emp,
            net_monthly_income=income,
            existing_emi_monthly=emi,
            bureau_score=score,
            total_experience_months=int(rng.triangular(0, 300, 60)),
            current_job_tenure_months=int(rng.triangular(0, 120, 24)),
            employer_category=rng.choice(["private_ltd", "govt", "psu", "mnc", "public_ltd"]),
            enquiries_last_6m=rng.choices([0, 1, 2, 5, 8], weights=[0.5, 0.25, 0.15, 0.07, 0.03])[0],
            max_dpd_last_12m=rng.choices([None, 0, 30, 60], weights=[0.4, 0.4, 0.12, 0.08])[0],
            writeoff_or_settled_24m=rng.random() < 0.05,
            city=rng.choice(["Mumbai", "Delhi", "Bengaluru", "Pune", "Jaipur", "Rourkela", "Lucknow"]),
            date_of_birth=_dob(age),
            application_date=APP_DATE,
        )
        if emp in ("sep", "seb"):
            kw["business_vintage_months"] = int(rng.triangular(0, 120, 36))
            kw["itr_years_filed"] = rng.choice([0, 1, 2, 3])
            if kw["itr_years_filed"] >= 1:
                kw["itr_income_y1"] = income * 12
        else:
            kw["business_vintage_months"] = None
        try:
            out.append(Applicant(**kw))
        except Exception:
            continue
    return out


@dataclass
class PopulationStats:
    n: int
    eligible_rate: float
    avg_offers: float
    per_lender_approval: dict[str, float]
    top_blocking: dict[str, int]


def run_population(apps: list[Applicant], engine: Engine | None = None) -> PopulationStats:
    engine = engine or Engine()
    from collections import Counter
    elig = 0
    offers_sum = 0
    approve: Counter = Counter()
    blocking: Counter = Counter()
    for a in apps:
        d = engine.run(a)
        if d.eligible:
            elig += 1
        appr = [o for o in d.offers if o.status.is_offer]
        offers_sum += len(appr)
        for o in appr:
            approve[o.lender_id] += 1
        for r in d.top_blocking_reasons:
            blocking[r.code] += 1
    n = len(apps)
    return PopulationStats(
        n=n,
        eligible_rate=elig / n if n else 0.0,
        avg_offers=offers_sum / n if n else 0.0,
        per_lender_approval={k: v / n for k, v in approve.most_common()},
        top_blocking=dict(blocking.most_common(10)),
    )
