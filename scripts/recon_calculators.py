"""Inspect each candidate eligibility calculator: list its input controls and result text.

This is reconnaissance only (no probing). Output: data/calibration/calculator_recon.json
Usage: .venv\\Scripts\\python.exe scripts/recon_calculators.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "calibration"

CANDIDATES = {
    "icici": "https://www.icici.bank.in/personal-banking/loans/personal-loan/eligibility",
    "idfc": "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/personal-loan-eligibility-calculator",
    "lnt": "https://www.ltfinance.com/personal-loan-eligibility-calculator",
    "tata": "https://www.tatacapital.com/personal-loan/eligibility-calculator.html",
    "bajaj": "https://www.bajajfinserv.in/personal-loan-eligibility-calculator",
    "kotak": "https://www.kotak.com/en/personal-banking/loans/personal-loan/eligibility.html",
    "axis": "https://www.axis.bank.in/loans/personal-loan",
    "hdfc": "https://www.hdfc.bank.in/personal-loan/eligibility-criteria",
    "abcl": "https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/eligibility-criteria",
    "poonawalla": "https://poonawallafincorp.com/personal-loan/interest-rates-and-charges",
    "indusind": "https://www.indusind.bank.in/in/en/personal/loans/personal-loan.html",
    "yes": "https://www.yes.bank.in/personal-banking/loans/personal-loan/eligibility-criteria",
    "moneyview": "https://moneyview.in/personal-loan-eligibility-check",
    "sbi": "https://sbi.bank.in/web/personal-banking/loans/personal-loans/sbi-personal-loan",
    "bob": "https://www.bankofbaroda.in/personal-banking/loans/personal-loan/baroda-personal-loan",
}

CHILD = r'''
import json, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, "scripts")
from snapshot_sources import UA
url, headed = sys.argv[1], sys.argv[2] == "1"
JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
                     return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const lab = e => { let t = '';
    if (e.id) { const l = document.querySelector('label[for="' + e.id + '"]'); if (l) t = l.innerText; }
    if (!t && e.getAttribute('aria-label')) t = e.getAttribute('aria-label');
    if (!t) { const p = e.closest('div,li,section'); if (p) t = p.innerText.slice(0, 80); }
    return (t || '').replace(/\\s+/g, ' ').trim().slice(0, 80); };
  return Array.from(document.querySelectorAll('input,select')).filter(vis).map(e => ({
    tag: e.tagName, type: e.type || '', name: e.name || '', id: e.id || '', min: e.min || '', max: e.max || '',
    value: e.value || '', placeholder: e.placeholder || '', label: lab(e)
  })).filter(x => !['hidden','submit','button','checkbox','radio','search','email','tel','password'].includes(x.type));
}"""
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=not headed, args=["--disable-blink-features=AutomationControlled"] if headed else [])
    p = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}).new_page()
    p.goto(url, timeout=45000, wait_until="domcontentloaded")
    try: p.wait_for_load_state("networkidle", timeout=12000)
    except Exception: pass
    p.mouse.wheel(0, 2500); p.wait_for_timeout(2500)
    print(json.dumps({"inputs": p.evaluate(JS), "frames": [f.url for f in p.frames][:8]}))
    b.close()
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child = OUT / "_recon_child.py"
    child.write_text(CHILD, encoding="utf-8")
    report = {}
    for lender, url in CANDIDATES.items():
        headed = "yes.bank.in" in url
        try:
            r = subprocess.run([sys.executable, str(child), url, "1" if headed else "0"], capture_output=True,
                               text=True, timeout=110, encoding="utf-8", errors="replace", cwd=ROOT)
            data = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-300:]}
        except subprocess.TimeoutExpired:
            data = {"error": "timeout"}
        except Exception as exc:
            data = {"error": str(exc)[:300]}
        report[lender] = {"url": url, **data}
        n = len(data.get("inputs", [])) if isinstance(data, dict) else 0
        print(f"{lender:<11} inputs={n:<3} {data.get('error', '')[:80]}", flush=True)
    child.unlink()
    (OUT / "calculator_recon.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
