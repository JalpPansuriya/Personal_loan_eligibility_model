"""Rebuild data/sources/index.csv from snapshot files on disk.

Each .md snapshot carries its source URL and access time in its header comment.
PDFs carry no header, so their URL is recovered from SOURCES in snapshot_sources.py
by matching the slugged filename.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from snapshot_sources import OUT, SOURCES, slug

HDR = re.compile(r"<!-- source: (?P<url>\S+)\s+accessed_utc: (?P<ts>\S+)")


def main() -> None:
    by_slug = {(lender, slug(u)): u for lender, urls in SOURCES.items() for u in urls}
    rows = []
    for f in sorted(OUT.iterdir()):
        if f.name == "index.csv" or f.suffix not in (".md", ".pdf"):
            continue
        lender, rest = f.name.split("__", 1)
        s, day = rest.rsplit("__", 1)
        if f.suffix == ".md":
            m = HDR.search(f.read_text(encoding="utf-8")[:600])
            url, ts = (m["url"], m["ts"]) if m else (by_slug.get((lender, s), ""), day[:10])
            chars = len(f.read_text(encoding="utf-8"))
        else:
            url, ts, chars = by_slug.get((lender, s), ""), day[:10], f.stat().st_size
        rows.append({"lender": lender, "url": url, "file": f.name, "status": "ok",
                     "accessed_utc": ts, "chars": str(chars)})
    with (OUT / "index.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["lender", "url", "file", "status", "accessed_utc", "chars"])
        w.writeheader()
        w.writerows(rows)
    missing = [(l, u) for l, us in SOURCES.items() for u in us if u not in {r["url"] for r in rows}]
    print(f"{len(rows)} snapshots indexed; {len(missing)} configured URLs without a snapshot")
    for l, u in missing:
        print("  MISSING", l, u)


if __name__ == "__main__":
    main()
