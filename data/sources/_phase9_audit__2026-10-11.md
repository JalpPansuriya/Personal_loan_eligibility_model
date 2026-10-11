# Phase 9 — provenance audit, generic-default review, live risk-lender re-check (2026-10-11)

## Generic / estimated material rules (audit)
`scripts/audit_generic_defaults.py` lists every material sizing/pricing/gate rule that is
NOT published. Current total: **187 non-published material rules** across the 20 lenders,
every one tagged `estimated` or `derived` (never `published`) with an `estimation_method`
note. None is presented as a verified lender rule. The largest generic groups:

- `income_multiple_max` 38 rows — mostly "default 18-20x NMI pending calculator probe".
- `foir_max` 38 rows — default 60% where the lender publishes no FOIR.
- `score_min` 22 rows, `loan_min` 9 rows — conservative defaults.

These are the honest gaps: the engine flags them (MAX_AMOUNT_ESTIMATED, GROSS_INCOME_ESTIMATED)
and never claims a lender is fully verified when its material rules are assumptions
(`/api/summary` → material_rules_verified / _estimated / _inferred / _conflict).

## Live risk-lender re-check (confirming plan3 cases)
- **Canara Budget**: official net-take-home rule confirmed (NTH ≥ max(25% net, ₹10,000)).
  The engine now applies the take-home / FOIR caps on NET income (not a net→gross estimate),
  so the high-EMI applicant's max fell from ₹25.05L to ₹11.78L and is flagged
  GROSS_INCOME_ESTIMATED. Published ceilings 50L (prime) / 40L (delight) still bind;
  "higher quantum selectively" remains a flagged, non-automatic exception.
- **KreditBee**: published range 12%–27.5%. The engine no longer prices above 27.5% on an
  adverse bureau profile; it clamps to the ceiling and flags RATE_AT_RANGE_CEILING.
- **Union** (women-professional / professional): require declared gender / profession before
  the product can be judged (GENDER_REQUIRED / PROFESSION_REQUIRED → ADDITIONAL_INFORMATION_REQUIRED),
  never inferred from a free-text description.
- **PNB / SBI**: public-scheme caps (₹20L / ₹50L) unchanged and consistent with the cached
  official pages; segment/employer/check-off conditions remain product-scoped, not universal.

## Change detection
`scripts/check_source_drift.py` hashes every snapshot into `_snapshot_manifest.json`. A hash
mismatch (local tampering or a refreshed capture) writes a review queue (`_drift_review.md`);
changes are NEVER auto-accepted as a verified policy change — a human must confirm each before
any rule value is edited.
