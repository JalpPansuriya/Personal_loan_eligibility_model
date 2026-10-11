"""Snapshot every lender source page to data/sources/ with URL + access timestamp.

Usage:  .venv\\Scripts\\python.exe scripts/snapshot_sources.py [lender ...] [--force]
Each page is captured in its own child process (scripts/_capture_one.py) with a hard
timeout, so one hung site cannot stall the run. Already-captured pages are skipped
unless --force. Full DOM text (incl. hidden tabs/accordions) is saved as .md; PDFs as-is.
Run scripts/rebuild_index.py afterwards to regenerate data/sources/index.csv.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sources"

SOURCES: dict[str, list[str]] = {
    "sbi": [
        "https://sbi.bank.in/web/personal-banking/loans/personal-loans/sbi-personal-loan",
        "https://sbi.co.in/web/faq-s/faq-personal-loan/",
        "https://sbi.bank.in/web/interest-rates/interest-rates/loan-schemes-interest-rates/personal-loans-schemes",
    ],
    "hdfc": [
        "https://www.hdfc.bank.in/personal-loan/eligibility-criteria",
        "https://www.hdfc.bank.in/personal-loan",
        "https://www.hdfc.bank.in/personal-loan/interest-rates-and-charges",
    ],
    "icici": [
        "https://www.icici.bank.in/personal-banking/loans/personal-loan/eligibility",
        "https://www.icici.bank.in/personal-banking/loans/personal-loan",
        "https://www.icici.bank.in/personal-banking/loans/personal-loan/personal-loan-interest-rates",
        "https://www.icici.bank.in/personal-banking/loans/personal-loan/service-charges",
    ],
    "axis": [
        "https://www.axis.bank.in/loans/personal-loan",
        "https://www.axis.bank.in/loans/personal-loan/eligibility-documentations",
        "https://www.axis.bank.in/loans/personal-loan/interest-rates-charges",
    ],
    "kotak": [
        "https://www.kotak.com/en/personal-banking/loans/personal-loan/eligibility.html",
        "https://www.kotak.com/en/personal-banking/loans/personal-loan.html",
        "https://www.kotak.com/en/personal-banking/loans/personal-loan/interest-rates.html",
        "https://www.kotak.com/en/personal-banking/loans/personal-loan/fees-and-charges.html",
    ],
    "bob": [
        "https://www.bankofbaroda.in/personal-banking/loans/personal-loan/baroda-personal-loan",
    ],
    "pnb": [
        "https://pnb.bank.in/personalloanforpublic.html",
        "https://pnb.bank.in/Retail-Advances-interst-rate-on-advances-linked-to-mclr.html",
        "https://pnb.bank.in/interst-rate-on-advances-linked-to-mclr.html",
        "https://pnb.bank.in/service-charges-related-to-retail-advances.html",
        "https://pnb.bank.in/FAQ-PERSONAL-LOAN.html",
        "https://pnb.bank.in/NTBPL.html",
    ],
    "canara": [
        "https://www.canarabank.bank.in/canara-budget",
        "https://www.canarabank.bank.in/rates-of-interest-for-retail-lending-schemes-linked-to-rllr",
        "https://www.canarabank.bank.in/interest-for-retail-lending-schemes-linked-to-fixed-rate-of-interest",
        "https://www.canarabank.bank.in/pages/interest-rate-range-on-loans",
    ],
    "union": [
        "https://unionbankofindia.bank.in/en/Details/union-personal-salaried-individual-other-than-government-employee",
        "https://unionbankofindia.bank.in/en/Details/union-personal-loan-non-salaried",
        "https://unionbankofindia.bank.in/en/Details/union-professional-personal-loan-scheme",
        "https://unionbankofindia.bank.in/en/Details/union-women-professional-personal-loan-scheme",
        "https://unionbankofindia.bank.in/en/Details/personal-loan-under-special-retail-lending-scheme-for-government-employees",
        "https://unionbankofindia.bank.in/pdf/retail_roi.pdf",
        "https://unionbankofindia.bank.in/pdf/Service%20Charges-Domestic%20Rupee%20Advances-Corp%20Website.pdf",
    ],
    "indusind": [
        "https://www.indusind.bank.in/in/en/personal/loans/personal-loan.html",
        "https://www.indusind.bank.in/in/en/personal/loans/personal-loan/personal-loan-interest-rate.html",
        "https://www.indusind.bank.in/content/dam/indusind-corporate/schedule-of-charges/others/Personal-Loan-SOC.pdf",
    ],
    "idfc": [
        "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan",
        "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/higher-limit",
        "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/personal-loan-interest-rates",
        "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/fees-and-charges",
        "https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/personal-loan-eligibility-calculator",
    ],
    "yes": [
        "https://www.yes.bank.in/personal-banking/loans/personal-loan",
        "https://www.yes.bank.in/personal-banking/loans/personal-loan/eligibility-criteria",
        "https://www.yes.bank.in/personal-banking/loans/personal-loan/interest-rates",
        "https://www.yes.bank.in/pdf?name=ybl_pl%20_kfs_english.pdf",
    ],
    "bajaj": [
        "https://www.bajajfinserv.in/personal-loan",
        "https://www.bajajfinserv.in/minimum-salary-required-for-personal-loan",
        "https://www.bajajfinserv.in/personal-loan-eligibility-calculator",
        "https://www.bajajfinserv.in/personal-loan-for-self-employed",
        "https://cms-assets.bajajfinserv.in/is/content/bajajfinance/interest-rate-policy-march-2026-final?scl=1&fmt=pdf",
    ],
    "tata": [
        "https://www.tatacapital.com/personal-loan/eligibility-calculator.html",
        "https://www.tatacapital.com/personal-loan/rates-and-charges.html",
        "https://www.tatacapital.com/personal-loan.html",
        "https://www.tatacapital.com/personal-loan/documents-required.html",
    ],
    "abcl": [
        "https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/eligibility-criteria",
        "https://www.adityabirlacapital.com/loans/personal-finance/personal-loan",
        "https://www.adityabirlacapital.com/loans/personal-finance",
        "https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/interest-rates",
        "https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/loan-for-self-employed",
        "https://www.adityabirlacapital.com/-/media/ABCL/pdf/Aditya-Birla-Finance-Limited/ABCL-Interest-rate-policy-V4.ashx",
    ],
    "lnt": [
        "https://www.ltfinance.com/personal-loan",
        "https://www.ltfinance.com/personal-loan-eligibility-calculator",
        "https://www.ltfinance.com/personal-loan-for-salaried",
        "https://www.ltfinance.com/personal-loan-for-self-employed",
        "https://www.ltfinance.com/personal-loan-interest-rate",
        "https://www.ltfinance.com/personal-loan-fees-and-charges",
    ],
    "poonawalla": [
        "https://poonawallafincorp.com/personal-loan/eligibility-and-documents",
        "https://poonawallafincorp.com/personal-loan/interest-rates-and-charges",
        "https://poonawallafincorp.com/personal-loan/prime-personal-loan-for-salaried-employees",
        "https://poonawallafincorp.com/instant-personal-loan/eligibility-and-document",
        "https://poonawallafincorp.com/professional-loan/eligibility-and-documents",
    ],
    "navi": [
        "https://navi.com/terms-and-conditions/cash-loan",
        "https://navi.com/finserv",
        "https://navi.com/finserv/lsp-dla",
        "https://navi.com/personal-loan",
    ],
    "kreditbee": [
        "https://www.kreditbee.in/personal-loan",
        "https://www.kreditbee.in/personal-loan-for-salaried",
        "https://www.kreditbee.in/personal-loan-for-self-employed",
        "https://www.kreditbee.in/flexi-personal-loan",
    ],
    "moneyview": [
        "https://moneyview.in/personal-loan",
        "https://moneyview.in/loans-faq-en",
        "https://moneyview.in/our-lending-partners",
        "https://moneyview.in/loans/instant-personal-loan-for-self-employed",
        "https://moneyview.in/personal-loan-eligibility-check",
    ],
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# Hosts that block headless Chromium; captured with a visible (headed) browser instead.
HEADED_HOSTS = ("yes.bank.in",)

# Hosts that serve a generic shell to a reused browser session; each page gets a fresh context.
FRESH_CONTEXT_HOSTS = ("ltfinance.com",)

# Expand collapsed FAQ/accordion/tab content so answers are in the visible text.
# Many bank pages keep eligibility/fees/FAQ answers in hidden tabs (display:none);
# innerText skips hidden nodes, so we first click toggles, then force every element visible.
EXPAND_JS = """
() => {
  document.querySelectorAll('details').forEach(d => d.open = true);
  const sel = '[aria-expanded="false"], .accordion-button.collapsed, .faq-question, .accordion__title';
  document.querySelectorAll(sel).forEach(el => { try { el.click(); } catch (e) {} });
  const style = document.createElement('style');
  style.textContent = '*{display:revert !important;visibility:visible !important;max-height:none !important;height:auto !important;overflow:visible !important;opacity:1 !important}'
    + ' script,style,noscript,template,svg,head,iframe{display:none !important}';
  document.head.appendChild(style);
  document.querySelectorAll('[hidden]').forEach(el => el.removeAttribute('hidden'));
  document.querySelectorAll('[aria-hidden="true"]').forEach(el => el.setAttribute('aria-hidden', 'false'));
}
"""

# Text of the whole DOM, including hidden tabs/accordions (CSS cannot hide it from this walk).
# Block-level elements and table cells become line breaks so tables/lists stay readable.
DOM_TEXT_JS = """
() => {
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','SVG','HEAD','IFRAME']);
  const BLOCK = new Set(['P','DIV','LI','TR','H1','H2','H3','H4','H5','H6','SECTION','ARTICLE','HEADER','FOOTER','UL','OL','TABLE','BR','DT','DD','BLOCKQUOTE','TBODY','THEAD','FORM','NAV','ASIDE','MAIN','DETAILS','SUMMARY']);
  const out = [];
  const walk = (n) => {
    if (n.nodeType === 3) { out.push(n.nodeValue); return; }
    if (n.nodeType !== 1 || SKIP.has(n.tagName)) return;
    const isBlock = BLOCK.has(n.tagName);
    if (isBlock) out.push('\\n');
    for (const c of n.childNodes) walk(c);
    if (n.tagName === 'TD' || n.tagName === 'TH') out.push(' | ');
    if (isBlock) out.push('\\n');
  };
  walk(document.body);
  return out.join('').split('\\n').map(l => l.replace(/[ \\t\\u00a0]+/g, ' ').trim()).filter(l => l).join('\\n');
}
"""


def slug(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[-90:]


def is_pdf(url: str) -> bool:
    u = url.lower()
    return u.endswith(".pdf") or "fmt=pdf" in u or ".ashx" in u or "pdf?name=" in u


PAGE_TIMEOUT_S = 120  # hard kill per page; one hung site can no longer stall the run


def capture(url: str, headed: bool, out_path: Path) -> tuple[str, int]:
    """Capture one page in a child process. Returns (status, chars)."""
    cmd = [sys.executable, str(Path(__file__).with_name("_capture_one.py")), url, "1" if headed else "0", str(out_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=PAGE_TIMEOUT_S,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        return f"error: timeout after {PAGE_TIMEOUT_S}s", 0
    if r.returncode != 0:
        out_path.unlink(missing_ok=True)
        msg = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["unknown"])[-1]
        return f"error: {msg[:160]}", 0
    try:
        return "ok", int(json.loads(r.stdout.strip().splitlines()[-1])["chars"])
    except Exception:
        return "ok", out_path.stat().st_size if out_path.exists() else 0


def main(only: list[str] | None = None, force: bool = False) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = failed = skipped = 0
    for lender, urls in SOURCES.items():
        if only and lender not in only:
            continue
        for url in urls:
            ext = ".pdf" if is_pdf(url) else ".md"
            existing = list(OUT.glob(f"{lender}__{slug(url)}__*{ext}"))
            if existing and not force:
                skipped += 1
                continue
            for f in existing:
                f.unlink()
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fname = f"{lender}__{slug(url)}__{ts[:10]}{ext}"
            out_path = OUT / fname
            headed = any(h in url for h in HEADED_HOSTS)
            status, chars = capture(url, headed, out_path)
            if status == "ok" and ext == ".md":
                body = out_path.read_text(encoding="utf-8")
                mode = "headed" if headed else "headless"
                header = (f"<!-- source: {url}\n     accessed_utc: {ts}\n     captured_by: scripts/snapshot_sources.py "
                          f"({mode} Chromium, full DOM text incl. hidden tabs/accordions) -->\n\n")
                out_path.write_text(header + body, encoding="utf-8")
            ok += status == "ok"
            failed += status != "ok"
            print(f"[{status[:5]}] {lender} {url} ({chars}) {'' if status == 'ok' else status}", flush=True)
    print(f"\n{ok} captured, {skipped} already present, {failed} failed")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    force = "--force" in argv
    sys.exit(main([a for a in argv if a != "--force"] or None, force=force))
