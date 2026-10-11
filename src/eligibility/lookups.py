"""Lookups: city -> tier, employer name -> category, profession allowlists, rate grids.

All are read-only CSVs under data/lookups/. City resolution is alias-aware and
case-insensitive. Everything is cached.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from . import paths


@lru_cache(maxsize=1)
def _city_table() -> dict[str, dict]:
    table: dict[str, dict] = {}
    with paths.CITY_TIER.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rec = {
                "city": r["city"],
                "engine_tier": int(r["engine_tier"]),
                "axis_serviced": str(r.get("axis_serviced", "")).strip().lower() == "true",
                "axis_tier": int(r["axis_tier"]) if r.get("axis_tier") else None,
            }
            table[r["city"].strip().lower()] = rec
            for alias in (r.get("aliases") or "").split("|"):
                alias = alias.strip().lower()
                if alias:
                    table[alias] = rec
    return table


def resolve_city(city: str | None) -> dict | None:
    """Return the city record (tier, axis service) or None if unresolved."""
    if not city:
        return None
    return _city_table().get(city.strip().lower())


def city_tier(city: str | None) -> int | None:
    rec = resolve_city(city)
    return rec["engine_tier"] if rec else None


def tier_band(city: str | None) -> str:
    """Map engine tier 1/2/3 to the metro|urban|semi_urban|rural vocabulary used in conditions.
    Tier 1 -> metro, tier 2 -> urban, tier 3 -> semi_urban. Unknown -> 'unknown'."""
    t = city_tier(city)
    return {1: "metro", 2: "urban", 3: "semi_urban"}.get(t, "unknown")


@lru_cache(maxsize=1)
def _employer_table() -> dict[tuple[str, str], set[str]]:
    """(lender_id, segment) -> set of allowed employer_category tokens."""
    table: dict[tuple[str, str], set[str]] = {}
    with paths.EMPLOYER_CATEGORY.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["lender_id"], r["segment"])
            table.setdefault(key, set()).add(r["employer_category"].strip().lower())
    return table


def employer_categories(lender_id: str, segment: str) -> set[str]:
    t = _employer_table()
    return t.get((lender_id, segment)) or t.get((lender_id, "all")) or set()


# a broad applicant-entered employer label expands to the equivalent allow-list tokens.
EMPLOYER_SYNONYMS: dict[str, set[str]] = {
    "govt": {"govt", "central_govt", "state_govt", "local_body", "autonomous", "psu",
             "psu_central", "psu_state", "psu_local_body", "joint_sector"},
    "psu": {"psu", "psu_central", "psu_state", "psu_local_body", "central_govt", "state_govt"},
    "defence": {"defence", "paramilitary", "capf", "coast_guard", "police", "railway"},
    "private": {"private", "private_ltd", "pvt_ltd", "public_ltd", "limited_company",
                "mnc", "listed_firm", "corporate", "reputed_corporate", "reputed_company",
                "private_institution", "recognized_organization", "registered_company"},
    "private_ltd": {"private_ltd", "pvt_ltd", "private", "limited_company"},
    "mnc": {"mnc", "corporate", "reputed_corporate", "public_ltd", "private_ltd"},
    "public_ltd": {"public_ltd", "listed_firm", "limited_company"},
    "corporate": {"corporate", "mnc", "private_ltd", "public_ltd", "reputed_corporate"},
}


def employer_matches(applicant_category: str | None, allowed: set[str]) -> bool:
    """True if the applicant's (possibly broad) employer label matches the allow-list,
    expanding common synonyms. Empty allow-list or empty label -> no block (handled by caller)."""
    if not applicant_category or not allowed:
        return True
    tok = applicant_category.strip().lower()
    if tok in allowed:
        return True
    return bool(EMPLOYER_SYNONYMS.get(tok, {tok}) & allowed)


@lru_cache(maxsize=1)
def _profession_table() -> dict[tuple[str, str], set[str]]:
    table: dict[tuple[str, str], set[str]] = {}
    with paths.PROFESSION_ALLOWLIST.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["lender_id"], r["segment"])
            table.setdefault(key, set()).add(r["profession"].strip().lower())
    return table


def professions(lender_id: str, segment: str) -> set[str]:
    return _profession_table().get((lender_id, segment), set())
