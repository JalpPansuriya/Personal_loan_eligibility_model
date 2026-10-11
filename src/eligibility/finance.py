"""Financial math primitives: EMI, present value of an annuity, and solving one from
the other. Pure functions, no engine state. Used by preprocess, affordability, pricing.

Convention: rates are annual nominal percentages (e.g. 10.5 means 10.5% p.a.), applied
monthly as r/1200 on a reducing balance (standard Indian retail loan maths).
"""
from __future__ import annotations


def monthly_rate(annual_pct: float) -> float:
    return annual_pct / 1200.0


def emi(principal: float, annual_pct: float, months: int) -> float:
    """EMI for a reducing-balance loan."""
    if months <= 0:
        raise ValueError("months must be positive")
    i = monthly_rate(annual_pct)
    if i == 0:
        return principal / months
    f = (1 + i) ** months
    return principal * i * f / (f - 1)


def pv_annuity(payment: float, annual_pct: float, months: int) -> float:
    """Principal that an affordable monthly `payment` can service over `months`.
    This is the max loan from an EMI-capacity figure (inverse of emi())."""
    if months <= 0:
        raise ValueError("months must be positive")
    if payment <= 0:
        return 0.0
    i = monthly_rate(annual_pct)
    if i == 0:
        return payment * months
    f = (1 + i) ** -months
    return payment * (1 - f) / i


def floor_to(value: float, step: int) -> float:
    """Floor a rupee amount to the nearest `step` (e.g. 10_000 for Kotak, 1_000 default)."""
    if step <= 0:
        return value
    return (int(max(value, 0)) // step) * step
