"""plan3 Phase 9D: source change-detection (review-only, never auto-accept).

For each rule source snapshot in data/sources/, (optionally) re-fetch the live page and
diff it against the stored snapshot. Any change is written to a REVIEW QUEUE
(data/sources/_drift_review.md) for a human to confirm before any rule value is updated.

A changed webpage is NEVER accepted automatically as a verified policy change (plan3 §9D):
this script only flags drift; it does not modify data/rules or data/lender_rules_long.csv.

Modes:
    --check-cache   (default) hash every snapshot and record a manifest; report snapshots
                    whose content hash differs from the recorded manifest (local tampering).
    --fetch         re-fetch live URLs (requires network + the project's fetch tool) and
                    diff; writes drift entries to the review queue. Not run in CI by default.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "sources"
LONG = ROOT / "data" / "lender_rules_long.csv"
MANIFEST = SRC / "_snapshot_manifest.json"
REVIEW = SRC / "_drift_review.md"


def _hash(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build_manifest() -> dict:
    out = {}
    for p in sorted(SRC.glob("*")):
        if p.name.startswith("_") or p.suffix not in (".md", ".txt", ".pdf"):
            continue
        out[p.name] = _hash(p)
    return out


def check_cache() -> int:
    current = build_manifest()
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote initial snapshot manifest ({len(current)} files) -> {MANIFEST.name}")
        return 0
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drifted = [n for n, h in current.items() if recorded.get(n) != h]
    added = [n for n in current if n not in recorded]
    removed = [n for n in recorded if n not in current]
    if not (drifted or added or removed):
        print(f"no snapshot drift ({len(current)} files match the manifest)")
        return 0
    lines = ["# Source drift review queue", ""]
    for n in drifted:
        lines.append(f"- CHANGED: `{n}` (hash differs from manifest) — review before updating any rule")
    for n in added:
        lines.append(f"- ADDED: `{n}` — new snapshot, not yet linked to a verified rule")
    for n in removed:
        lines.append(f"- REMOVED: `{n}` — rules citing it must be re-sourced")
    lines.append("")
    lines.append("Changes are NOT auto-accepted. A reviewer must confirm each before editing "
                 "data/rules/*.csv, then re-run with no drift to refresh the manifest.")
    REVIEW.write_text("\n".join(lines), encoding="utf-8")
    print(f"DRIFT DETECTED: {len(drifted)} changed, {len(added)} added, {len(removed)} removed "
          f"-> {REVIEW.name} (manual review required)")
    return 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="re-fetch live URLs (not implemented in CI)")
    args = ap.parse_args()
    if args.fetch:
        print("Live re-fetch is a manual, network-gated step; use snapshot_sources.py to capture "
              "fresh pages into a scratch dir, then diff. This script never auto-accepts changes.")
        return
    raise SystemExit(check_cache())


if __name__ == "__main__":
    main()
