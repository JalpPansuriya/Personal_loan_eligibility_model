# Personal Loan Eligibility Model — Top 20 Indian Lenders

A rule-based / scorecard engine (no machine learning) that takes one applicant and returns an
eligibility decision, a maximum loan, a priced offer (APR including fee + 18% GST), an
approval-strength score, and plain-English advice — for each of the 20 largest Indian personal-loan
lenders.

Why rule-based, not ML: there are no approval labels to learn from, and bureau/outcome data is
private. Inventing synthetic labels would just feed our own assumptions back to us. Instead every
rule is traced to a lender's own public page (saved, dated), and the two lenders with public
eligibility calculators (ICICI, Kotak) have their hidden sizing formulas **reverse-engineered** and
validated against held-out calculator outputs (mean error < 0.5%).

## Quick start (2 minutes)

```powershell
python -m venv .venv
.venv\Scripts\activate                 # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pip install -e .

# evaluate one of the 16 bundled sample profiles
python -m eligibility evaluate tests/profiles/P01.json --fixes

# machine-readable output
python -m eligibility evaluate tests/profiles/P03.json --json

# the HTTP API (FastAPI) that the React UI talks to
uvicorn eligibility.api:app --port 8000          # from an activated venv at repo root
#   GET  /api/meta      form metadata (enums, lenders, tenures)
#   GET  /api/profiles  the 16 sample inputs
#   POST /api/evaluate  applicant JSON -> full decision + fixes

# the React frontend (separate terminal; proxies /api to :8000)
cd frontend
npm install
npm run dev            # opens http://localhost:5173 (or 5174 if taken)

# the test suite (unit + property + calibration replay + golden + API)
pytest
```

## What the engine does

For each lender × product that offers the applicant's segment (salaried / self-employed
professional / self-employed business):

1. **Derive** the system features (age at application and maturity, income as the lender reads it,
   obligations, FOIR, score band, tenure cap).
2. **Hard gates** — age, income (city-tier aware), experience/vintage/ITR, score/NTC, employer and
   profession allow-lists, salary-account and city-service requirements, and a tiered bureau-hygiene
   policy. Missing applicant data does **not** silently pass: it yields
   `ADDITIONAL_INFORMATION_REQUIRED` (needed value absent) or `MANUAL_REVIEW` (ambiguous), while a
   documented violation yields `NOT_ELIGIBLE`.
3. **Size** the max eligible loan as the smallest of FOIR capacity, take-home-floor capacity,
   income multiple, and the product cap — recording which cap bound (`caps.binding_cap`). ICICI and
   Kotak use their calibrated calculator formula.
4. **Price** — the interest rate, processing fee, 18% GST on the fee, net disbursement, total
   repayment and the **APR by IRR** are kept as separate fields (APR is never rate + fee%). When the
   applicant's exact rate is unknown, the lender's published band is returned as a range.
5. **Quote amounts separately** — the engine returns a `requested` quote (amount, tenure, and the
   EMI for *that* principal/tenure) and a `max_eligible` quote (max amount, its tenure, and *its own*
   EMI). The two EMIs are never mixed.
6. **Explain & advise** — every decision carries its rule id, rule status (published/estimated),
   source URL and a suggested next action; the approval-strength score (0–100) never changes a gate;
   and a counterfactual search finds the smallest single change that would flip a rejection.

### Screening statuses (not bank approvals)

The engine screens published criteria; it does not issue sanctions, so no status says "approved":

| Status | Meaning |
|---|---|
| `ELIGIBLE_TO_QUERY_LENDERS` | passes all mandatory rules and is fully priced on published data |
| `PRELIMINARILY_ELIGIBLE` | passes the rules, but some terms are estimated/reduced or the rate is a range |
| `NOT_ELIGIBLE` | a documented mandatory rule is definitively violated |
| `ADDITIONAL_INFORMATION_REQUIRED` | a value needed to decide is missing |
| `MANUAL_REVIEW` | an ambiguous/unverified condition needs human interpretation |
| `INVALID_INPUT` | the applicant data failed validation |
| `RULES_UNAVAILABLE` | insufficient rule data to make a defensible decision |

The best option is the lowest-APR eligible product on the requested terms, with a stated rationale.
A `GET /api/summary` endpoint (and `python -m eligibility summary`) reports rule-base coverage
(lenders, products with published vs estimated rules, APR-reliable products) — these are coverage
figures, not approval rates.

## Repository layout

```
data/
  sources/              86 dated snapshots of lender pages + PDF text extractions
  rules/{lender}.csv    per-lender atomic rules (source of truth)
  lender_rules_long.csv merged rule table (1,259 rules) consumed by the engine
  conflicts.csv         variables where a lender's own pages disagree + the value used
  lookups/              city->tier, employer->category, profession allow-lists, rate grids
  calibration/          calculator probes + fitted parameters (ICICI, Kotak)
  variables.csv         the 34 features + data-driven coverage counts
src/eligibility/
  schema.py             Pydantic applicant / rule / decision models
  conditions.py         parser for the free-text rule conditions
  rules.py              rule store (load + index + condition pre-parse)
  lookups.py            city / employer / profession resolution
  preprocess.py         derived features F23-F34
  finance.py            EMI, PV annuity (reducing balance)
  calibration.py        fitted ICICI/Kotak calculator models
  affordability.py      loan sizing + binding-cap tracking
  pricing.py            rate band, fee+GST, APR by IRR, repricing
  strength.py           approval-strength scorecard (published weights)
  gates.py              hard-gate evaluation + tiered bureau policy
  engine.py             orchestration across all 20 lenders + best-offer pick
  counterfactual.py     minimal verified "how to qualify" advice
  simulate.py           synthetic population + sensitivity
  cli.py / __main__.py  command-line interface
  api.py                FastAPI HTTP API (/api/meta, /api/profiles, /api/evaluate)
frontend/               Vite + React + TypeScript UI (form -> 20-lender table + reasons/advice)
tests/                  phase gates, profiles P01-P16, golden baselines, API tests
```

## Frontend + backend

The UI is a React (Vite + TypeScript) single page that calls the FastAPI backend:

- Start the API: `uvicorn eligibility.api:app --port 8000`
- Start the UI: `cd frontend && npm install && npm run dev`

In development the Vite server proxies `/api/*` to `http://127.0.0.1:8000`, so the browser
sees a single origin. The form has a **"Paste JSON / load a sample profile"** box that
auto-fills every field from a pasted applicant payload or one of the 16 bundled profiles.
For production, `npm run build` emits static files in `frontend/dist/` that any static host
can serve against the same API.

## Testing

`pytest` runs everything (169 tests): data contracts, the condition parser over all real
conditions, boundary tests per gate, Hypothesis property tests, the **calibration replay**
(every ICICI/Kotak probe reproduced within tolerance), the 16 golden profiles, CLI smoke
tests, and the FastAPI endpoints.

## Honest limitations

- Internal scorecards, employer allow-lists and document checks are invisible to any outside model.
- Bureau-hygiene thresholds (DPD, enquiries, write-offs) are an **estimated** tiered policy, flagged
  as such and swept in the sensitivity analysis.
- Fintech pricing is personalised, so those ranges are wide and low-confidence.
- Rules change; every value is dated. This tool is **not** a loan offer.

See `model_report.md` for the full design, the feature catalogue, the calibration method, and the
P01–P16 worked examples.
