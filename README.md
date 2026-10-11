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

## How the 20 lenders were chosen

The goal was the 20 that matter most to a real Indian borrower, under a defensible,
reproducible method (full detail in `model_report.md` §3):

1. **Start from system size.** PL market totals and origination mix from CRIF "How India
   Lends" and Experian (banks vs NBFCs vs digital lenders by value and volume).
2. **Rank lenders by personal-loan book / AUM** from company presentations and reputable
   secondary sources, filling gaps with retail-book scale and origination presence.
3. **Require three things of every lender:** a genuine unsecured personal-loan product,
   public eligibility information, and a national or large-regional footprint.
4. **Enforce a market-representative mix** so the tool isn't all private banks:
   ≥5 PSU banks, ≥5 private banks, ≥4 NBFCs, and 2–3 fintechs (the brief explicitly allows
   fintechs, which dominate origination *volume*). Near-misses are documented.

The final set: **SBI, PNB, BoB, Canara, Union** (PSU); **HDFC, ICICI, Axis, Kotak, IndusInd,
IDFC First, Yes** (private); **Bajaj, Tata Capital, Aditya Birla, L&T, Poonawalla** (NBFC);
**Navi, KreditBee, Moneyview** (fintech). "Top 20 by scale," not "the 20 largest banks" —
the distinction is stated so the claim is honest.

## Approach

- **Rules as data, engine as code.** Every lender rule lives in `data/rules/{lender}.csv`
  as an atomic row (variable, operator, value, condition, source URL, date, confidence,
  verbatim quote). The engine is a generic evaluator over that table — adding or correcting
  a lender is a data edit, not a code change.
- **Provenance on every rule.** Each row is tagged `published`, `derived`, or `estimated`,
  and published rows carry a quote that must be an exact substring of a saved, dated page
  snapshot (`data/sources/`). A test (`verify_rules.py`) enforces this, so the engine cannot
  silently drift from the sources.
- **Pipeline per lender/product:** derive features → hard gates (incl. a tiered bureau
  policy) → size the maximum loan (min of FOIR, take-home-floor, income-multiple and product
  caps) → price (rate, fee, 18% GST, APR by IRR) → screening status + explanation + advice.
- **Conflict policy:** where a lender's own pages disagree, the engine uses the **stricter**
  value and keeps the alternative in `data/conflicts.csv` for sensitivity analysis.
- **No ML, by design.** There are no approval labels to learn from and real bureau/outcome
  data is private; synthetic labels would only echo our own assumptions back. The honest
  accuracy number is calibration error against real lender calculators (below).

## Assumptions, and how unlisted rules were found

**Finding rules that lenders don't publish.** Two lenders (ICICI, Kotak) expose public
eligibility *calculators* that output a maximum loan for a given income and obligations.
I probed each on a grid of inputs, held out ~20% of points, and least-squares-fitted the
hidden sizing formula:

- **Kotak:** `max_loan ≈ 20 × (net income − existing EMI)`, tenure-independent.
- **ICICI:** FOIR ≈ 70%, capitalised by an annuity factor ≈ 46.57, capped at ₹50L.

Both reproduce the held-out calculator outputs at **< 0.5% mean error**
(`tests/test_phase4_affordability.py` replays every probe). These are marked `derived`, not
published.

**Where a value genuinely isn't knowable from public sources, it is an explicit assumption**
(tagged `estimated`, never `published`), the main ones being:

- **Bureau hygiene** (DPD / enquiries / write-offs) — a tiered policy: banks reject on
  DPD ≥ 30, ≥ 6 enquiries, or a 24-month write-off/settlement; NBFCs reject on a write-off or
  DPD ≥ 60 and otherwise reprice (+3pp, 50% haircut); fintechs reprice (+5pp, 60% haircut),
  with KreditBee lenient. Swept in the sensitivity analysis.
- **FOIR / income-multiple** for lenders that publish neither (default FOIR 60%, multiple
  ≤ 20×), used only when no published or calibrated value exists.
- **Income reading:** gross-FOIR banks (BoB/PNB/Canara) read gross income; net is converted
  with `gross ≈ net / 0.75`. Credit-card load assumed at 5% of outstanding.
- **Rate within a published band** is placed by score band; when the applicant's exact rate
  is unknown the band is returned as a range, and the offer is `PRELIMINARILY_ELIGIBLE`.

## Insights

From a seeded synthetic population of 3,000 applicants (`eligibility.simulate`, reproducible
with `seed=42`) run through the real engine — 60,000 lender/applicant evaluations:

- **The credit score is the single biggest gate.** Of all `NOT_ELIGIBLE` outcomes, the
  primary reason is `SCORE_BELOW_MIN` **19%** of the time, ahead of
  `SEGMENT_NOT_OFFERED` (16%, i.e. salaried-only lenders turning away the self-employed),
  `NTC_NOT_ALLOWED` (13%), and `EMPLOYER_NOT_ALLOWED` (12%).
- **Unlisted bureau rules decide a lot of real cases.** `RECENT_DPD_GTE30` and
  `PRIOR_WRITEOFF_SETTLEMENT` together drive ~11% of rejections even though almost no lender
  publishes a numeric threshold — exactly the "rules that aren't listed" the brief asks about.
- **Lenders differ enormously in reach.** Fintechs approve the widest slice — KreditBee
  ~85%, Navi ~68%, Moneyview ~67% of the population at least preliminarily — while the
  strictest, PNB (check-off / listed-profession product), reaches ~1%, and Kotak ~11%.
  A typical applicant matches **~7 of 20** lenders.
- **What binds the loan size changes with the borrower.** For thin-income applicants FOIR or
  the take-home-floor binds; for high earners the product cap binds (multiples stop mattering).
  The engine records `caps.binding_cap` on every offer so this is visible, not guessed.
- **Shopping around is worth real money.** On the same prime profile the APR spread across
  eligible lenders is several percentage points, and the lowest headline *rate* is often not
  the lowest *APR* once the processing fee + GST are included — which is why ranking is by APR.

## Limits, and what I would add next

**Limits**

- Internal scorecards, employer allow-lists, and document checks are invisible to any
  outside model; the engine screens *published* criteria and never asserts a bank sanction.
- Bureau-hygiene thresholds and some FOIR/multiple values are estimated (flagged as such).
- Fintech pricing is personalised, so those APRs are wide, low-confidence ranges.
- A few self-employed rules (e.g. parts of Union's schemes) aren't on the live pages and
  stay `estimated`.
- The synthetic population uses assumed marginals; its shares are illustrative, not official.
- Rules change constantly — every value is dated, and the snapshots will go stale.

**What I would add next**

1. A scheduled re-crawl that re-verifies quotes against fresh snapshots and flags drift.
2. Probe more calculators (several banks have OTP-gated ones) to convert `estimated`
   FOIR/multiples into `derived`.
3. Real-rate personalisation once a bureau feed is available, replacing band placement.
4. A richer best-option view (total-cost-of-credit and net-disbursement ranking, not APR
   alone) and savings-vs-runner-up messaging.
5. CI that runs `verify_rules.py` + `pytest` on every data edit, so a bad rule can't merge.

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

`pytest` runs everything (193 tests): data contracts, the condition parser over all real
conditions, boundary tests per gate, Hypothesis property tests, the **calibration replay**
(every ICICI/Kotak probe reproduced within tolerance), the 16 golden profiles, the audit
regression/consistency invariants, CLI smoke tests, and the FastAPI endpoints.

See `model_report.md` for the full design, the feature catalogue, the calibration method, and the
P01–P16 worked examples. The limitations above are enforced in data and surfaced in the UI — every
estimated value is flagged, and no result is a loan offer.
