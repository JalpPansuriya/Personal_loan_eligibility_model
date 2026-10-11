"""Capture ONE page to stdout as JSON. Run as a child process so a hung page can be killed.

Usage: python scripts/_capture_one.py <url> <headed:0|1> <out_path>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snapshot_sources import DOM_TEXT_JS, EXPAND_JS, UA, is_pdf  # noqa: E402


def main() -> None:
    url, headed, out_path = sys.argv[1], sys.argv[2] == "1", Path(sys.argv[3])
    with sync_playwright() as pw:
        args = ["--disable-blink-features=AutomationControlled"] if headed else []
        browser = pw.chromium.launch(headless=not headed, args=args)
        ctx = browser.new_context(user_agent=UA)
        ctx.set_default_timeout(30000)
        if is_pdf(url):
            if headed:  # bot-checked hosts: warm up a session first
                p = ctx.new_page()
                p.goto(url.split("/pdf")[0], timeout=45000, wait_until="domcontentloaded")
            resp = ctx.request.get(url, timeout=60000)
            body = resp.body()
            if not resp.ok or body[:4] != b"%PDF":
                raise SystemExit(f"not a PDF (HTTP {resp.status}, starts {body[:12]!r})")
            out_path.write_bytes(body)
            print(json.dumps({"chars": len(body)}))
        else:
            page = ctx.new_page()
            resp = page.goto(url, timeout=45000, wait_until="domcontentloaded")
            if resp is not None and resp.status >= 400:
                raise SystemExit(f"HTTP {resp.status}")
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            before = page.evaluate(DOM_TEXT_JS)
            after = ""
            try:
                page.evaluate(EXPAND_JS)
                page.wait_for_timeout(1500)
                after = page.evaluate(DOM_TEXT_JS)
            except Exception:
                pass
            text = before if (not after or after == before) else (
                before + "\n\n<!-- ===== after expanding toggles ===== -->\n\n" + after)
            out_path.write_text(text, encoding="utf-8")
            print(json.dumps({"chars": len(text)}))
        browser.close()


if __name__ == "__main__":
    main()
