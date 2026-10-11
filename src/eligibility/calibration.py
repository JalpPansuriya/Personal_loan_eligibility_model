"""Calibrated sizing parameters recovered from lender calculators (Phase 4 input).

Only ICICI and Kotak expose a public eligibility calculator that takes income + existing
EMI. scripts/fit_calibration.py fitted their hidden sizing rules and wrote the parameters
to data/calibration/fit_report.csv. This module reads that file so the engine's loan
sizing for those two lenders is provably the fitted model (the calibration-replay gate
re-checks every probe against it).

Fitted models:
  kotak:  max_loan = floor_10k( multiple * (income - existing_emi) )            [tenure-independent]
  icici:  max_loan = min(cap, floor_10k( annuity_factor * (foir*income - existing_emi) ))
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from . import paths
from .finance import floor_to


@dataclass(frozen=True)
class KotakParams:
    multiple: float
    round_step: int = 10_000


@dataclass(frozen=True)
class IciciParams:
    annuity_factor: float
    foir: float
    cap: float
    round_step: int = 10_000


def _parse_params(blob: str) -> dict[str, str]:
    out = {}
    for part in blob.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


@lru_cache(maxsize=1)
def _fit_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (paths.CALIBRATION / "fit_report.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r["lender"]] = r
    return rows


@lru_cache(maxsize=1)
def kotak_params() -> KotakParams:
    p = _parse_params(_fit_rows()["kotak"]["params"])
    return KotakParams(multiple=float(p["multiple_net_of_obligations"]))


@lru_cache(maxsize=1)
def icici_params() -> IciciParams:
    p = _parse_params(_fit_rows()["icici"]["params"])
    return IciciParams(annuity_factor=float(p["annuity_factor"]), foir=float(p["foir"]),
                       cap=float(p["cap"]))


def kotak_max_loan(income: float, existing_emi: float) -> float:
    k = kotak_params()
    return floor_to(k.multiple * (income - existing_emi), k.round_step)


def icici_max_loan(income: float, existing_emi: float) -> float:
    c = icici_params()
    raw = c.annuity_factor * (c.foir * income - existing_emi)
    return min(c.cap, floor_to(raw, c.round_step))


def holdout_mape() -> dict[str, float]:
    return {k: float(v["holdout_mape_pct"]) for k, v in _fit_rows().items()}
