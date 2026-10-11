"""Filesystem locations for the data layer, resolved relative to the repo root.

Every module reads data through these constants so the package works regardless of
the current working directory.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCES = DATA / "sources"
RULES_DIR = DATA / "rules"
LOOKUPS = DATA / "lookups"
RATE_GRIDS = LOOKUPS / "rate_grids"
CALIBRATION = DATA / "calibration"

RULES_LONG = DATA / "lender_rules_long.csv"
RULES_WIDE = DATA / "lender_rules_wide.csv"
CONFLICTS = DATA / "conflicts.csv"
VARIABLES = DATA / "variables.csv"
COVERAGE_MATRIX = DATA / "coverage_matrix.csv"

CITY_TIER = LOOKUPS / "city_tier.csv"
EMPLOYER_CATEGORY = LOOKUPS / "employer_category.csv"
PROFESSION_ALLOWLIST = LOOKUPS / "profession_allowlist.csv"


def exists_report() -> dict[str, bool]:
    """Quick existence check for the data contract (used by Phase 0 tests)."""
    return {
        p.name: p.exists()
        for p in (RULES_LONG, RULES_WIDE, CONFLICTS, VARIABLES, COVERAGE_MATRIX,
                  CITY_TIER, EMPLOYER_CATEGORY, PROFESSION_ALLOWLIST)
    }
