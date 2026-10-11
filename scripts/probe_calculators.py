"""Probe lender eligibility calculators with controlled inputs (public pages, no login/OTP).

Calculators that take income + existing EMI and return a max loan (found by
scripts/recon_calculators.py and checked by hand): ICICI, Kotak. Other lenders'
pages either expose only EMI calculators (amount/rate/tenure -> EMI, which reveal no
eligibility rule) or gate the result behind OTP/login, which the brief forbids.

Each probe sets income / existing EMI / tenure, reads the returned max loan and writes one
row. A fixed 20% of points (deterministic hash) are tagged holdout=1; the fitting step
must never use them, and they are reserved for the accuracy check.

Output: data/calibration/probes_{lender}_{date}.csv
Usage:  .venv\\Scripts\\python.exe scripts/probe_calculators.py [lender ...]
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "calibration"

URLS = {
    "icici": "https://www.icici.bank.in/personal-banking/loans/personal-loan/eligibility",
    "kotak": "https://www.kotak.com/en/personal-banking/loans/personal-loan/eligibility.html",
}
# ICICI requires an employer from its published list (organizations.json); we probe a large
# listed employer and a smaller one to see whether employer category changes the answer.
ICICI_EMPLOYERS = ["INFOSYS LIMITED", "TATA CONSULTANCY SERVICES LIMITED", "STATE BANK OF INDIA"]

INCOMES = [25000, 40000, 60000, 80000, 100000, 150000, 200000, 300000]
EMI_SHARES = [0.0, 0.15, 0.30, 0.45]
TENURE_YEARS = [3, 5]


def grid(lender: str) -> list[dict]:
    pts = []
    employers = ICICI_EMPLOYERS if lender == "icici" else [""]
    tenures = [None] if lender == "icici" else TENURE_YEARS  # ICICI form has no tenure input
    for emp in employers:
        for inc in INCOMES:
            for share in EMI_SHARES:
                for ty in tenures:
                    pts.append({"employer": emp, "income": inc, "existing_emi": int(round(inc * share, -2)),
                                "tenure_years": ty if ty is not None else ""})
    for p in pts:
        key = f"{lender}|{p['employer']}|{p['income']}|{p['existing_emi']}|{p['tenure_years']}"
        p["holdout"] = int(int(hashlib.sha1(key.encode()).hexdigest(), 16) % 5 == 0)
    return pts


DRIVER = r'''
import json, re, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, "scripts")
from snapshot_sources import UA
lender, url, pts = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])

KILL = "() => document.querySelectorAll('[class*=interstitial]').forEach(e => e.remove())"
SET = """([sel, idx, val]) => {
  const el = document.querySelectorAll(sel)[idx]; if (!el) return null;
  const proto = el.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, String(val));
  ['input','change','keyup','blur'].forEach(t => el.dispatchEvent(new Event(t, {bubbles: true})));
  return el.value; }"""

def rupees(s):
    m = re.search(r"₹\s*([0-9][0-9,]*)", s)
    return float(m.group(1).replace(",", "")) if m else None

def typed(page, loc, val):
    loc.scroll_into_view_if_needed(); loc.click(force=True)
    loc.press("Control+A"); loc.press("Backspace"); loc.type(str(val), delay=25); loc.press("Tab")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}).new_page()
    page.set_default_timeout(15000)
    page.goto(url, timeout=45000, wait_until="domcontentloaded")
    try: page.wait_for_load_state("networkidle", timeout=12000)
    except Exception: pass
    page.wait_for_timeout(2500)
    page.evaluate(KILL)
    current_emp = None
    for i, p in enumerate(pts):
        try:
            if lender == "icici":
                boxes = page.locator("input#rangeSliderVal")
                typed(page, boxes.nth(0), p["income"])
                typed(page, boxes.nth(1), p["existing_emi"])
                if p["employer"] != current_emp:
                    org = page.locator("input#searchOrg").first
                    typed(page, org, p["employer"].split()[0])
                    page.wait_for_timeout(2500)
                    # pick via DOM click: the dropdown item is often covered by the result card
                    picked = page.evaluate("""(name) => {
                      const it = Array.from(document.querySelectorAll('li.searchOrg__item'))
                        .find(e => e.innerText.trim().toUpperCase() === name.toUpperCase());
                      if (!it) return false; it.click(); return true; }""", p["employer"])
                    if not picked:
                        raise RuntimeError("employer not in dropdown: " + p["employer"])
                    current_emp = p["employer"]
                page.wait_for_timeout(2500)
                t = page.evaluate("document.body.innerText")
                m = re.search(r"eligible for a total loan amount of\s*(₹\s*[0-9,\-]+)", t)
                raw = m.group(0) if m else "result text not found"
                val = rupees(m.group(1)) if m else None
            elif lender == "kotak":
                rng = page.locator("input#myRange")
                for idx, v in ((0, p["income"]), (1, p["existing_emi"]), (2, int(p["tenure_years"]) * 12)):
                    page.evaluate(SET, ["input#myRange", idx, v])
                page.wait_for_timeout(1500)
                blk = rng.first.evaluate("e => { let q = e; for (let k = 0; k < 8 && q; k++) q = q.parentElement; return q ? q.innerText : ''; }")
                blk = " ".join(blk.split())
                m = re.search(r"Loan Eligible Amount\s*(₹\s*[0-9,]+)", blk)
                raw = blk[:260]
                val = rupees(m.group(1)) if m else None
            print(json.dumps({"i": i, "max_loan": val, "raw": raw}), flush=True)
        except Exception as exc:
            print(json.dumps({"i": i, "max_loan": None, "raw": "ERROR " + str(exc).splitlines()[0][:200]}), flush=True)
    b.close()
'''


def run(lender: str, employers: list[str] | None = None, tag: str = "") -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    pts = grid(lender)
    if employers:
        pts = [p for p in pts if p["employer"] in employers]
    child = OUT / f"_probe_child_{lender}.py"
    child.write_text(DRIVER, encoding="utf-8")
    lines, err = [], ""
    try:
        r = subprocess.run([sys.executable, str(child), lender, URLS[lender], json.dumps(pts)],
                           capture_output=True, text=True, timeout=90 + 15 * len(pts),
                           encoding="utf-8", errors="replace", cwd=ROOT)
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
        err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
        err = "timeout"
    finally:
        child.unlink(missing_ok=True)
    by_i = {x["i"]: x for x in lines}
    path = OUT / f"probes_{lender}{tag}_{date.today().isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["lender", "url", "probed_on", "employer", "income", "existing_emi",
                                           "tenure_years", "holdout", "max_loan", "raw"])
        w.writeheader()
        for i, p in enumerate(pts):
            res = by_i.get(i, {"max_loan": None, "raw": f"no result ({err[:80]})"})
            w.writerow({"lender": lender, "url": URLS[lender], "probed_on": date.today().isoformat(), **p,
                        "max_loan": "" if res["max_loan"] is None else res["max_loan"], "raw": res["raw"]})
    got = sum(1 for i in range(len(pts)) if by_i.get(i, {}).get("max_loan") is not None)
    print(f"{lender:<6} {got}/{len(pts)} points returned a value -> {path.name} {err[:100]}", flush=True)
    return path


if __name__ == "__main__":
    # usage: probe_calculators.py kotak | icici [EMPLOYER NAME] (one employer per run keeps runs short)
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "icici":
        emp = " ".join(args[1:])
        run("icici", [emp], tag="-" + emp.split()[0].lower())
    else:
        for lender in (args or list(URLS)):
            run(lender)
