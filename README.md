# Personal Loan Eligibility Model — 20 Selected Indian Lenders

A rule-based / scorecard engine (no machine learning) that takes one applicant and returns an
eligibility decision, a maximum loan, a priced offer (interest rate, fee, 18% GST and an **APR
computed by IRR** on net-of-fee cash flows — never rate + fee%), a transparent rule-fit score,
and plain-English advice — for each of 20 selected Indian personal-loan lenders.

The engine distinguishes eligibility for a *product* from eligibility for the applicant's *exact
requested amount and tenure*: the requested terms are never silently rewritten, and any reduced
amount/tenure is shown as a separate, clearly labelled alternative — not a sanction.

**Why rule-based, not ML:** there are no approval labels to learn from, and bureau/outcome data is
private. Inventing synthetic labels would just feed our own assumptions back to us. Instead every
rule is traced to a lender's own public page (saved, dated), and the two lenders with public
eligibility calculators (ICICI, Kotak) have their hidden sizing formulas **reverse-engineered** and
validated against held-out calculator outputs (mean error < 0.5%).

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate                 # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pip install -e .

# evaluate a bundled sample profile
python -m eligibility evaluate tests/profiles/P01.json --fixes
python -m eligibility evaluate tests/profiles/P03.json --json   # machine-readable

# the HTTP API (FastAPI) that the React UI talks to
uvicorn eligibility.api:app --port 8000
#   GET  /api/meta         form metadata (enums, lenders, tenures)
#   GET  /api/profiles     the bundled sample inputs
#   GET  /api/summary      rule-base coverage + completeness
#   GET  /api/completeness per-product rule completeness
#   POST /api/evaluate     applicant JSON -> full decision + fixes

# the React frontend (separate terminal; proxies /api to :8000)
cd frontend
npm install
npm run dev            # http://localhost:5173

# tests
pytest                 # backend
cd frontend && npm test   # frontend input-mapping suite
```

## What the engine does

For each lender × product that offers the applicant's segment (salaried / self-employed
professional / self-employed business):

1. **Derive** the features (age at application and maturity, income as the lender reads it,
   obligations, FOIR, score band, tenure cap).
2. **Hard gates** — age, income (city-tier aware), experience/vintage/ITR, score/NTC, employer and
   profession allow-lists, salary-account and city-service requirements, and a tiered bureau-hygiene
   policy. Missing applicant data does **not** silently pass: it yields
   `ADDITIONAL_INFORMATION_REQUIRED` (needed value absent) or `MANUAL_REVIEW` (ambiguous), while a
   documented violation yields `NOT_ELIGIBLE`. Product-specific attributes (gender, profession) are
   never inferred from free text.
3. **Size** the max eligible loan as the smallest of FOIR capacity, take-home-floor capacity,
   income multiple, and the product cap — recording which cap bound (`caps.binding_cap`). ICICI and
   Kotak use their calibrated calculator formula. A max resting on an estimated rule is flagged.
4. **Price** — the interest rate, processing fee, 18% GST on the fee, net disbursement, total
   repayment and the **APR by IRR** are kept as separate fields. The IRR equates the net disbursal
   (principal − fee − GST) to the EMI stream, following the RBI Key Facts Statement method.
   Time-bound fee waivers apply only when the application date is inside their effective window.
   Bureau repricing never exceeds a lender's published rate ceiling.
5. **Quote amounts separately** — a `requested` quote (the exact requested amount, tenure, and the
   EMI for *that* principal/tenure), a `max_eligible` quote (max amount, its tenure, and *its own*
   EMI), and, when the request isn't fully covered, an `alternative` quote. The EMIs are never
   mixed, and every displayed EMI names its principal, rate and tenure.
6. **Explain & advise** — every decision carries a per-rule trace (`checks[]`, each PASS/FAIL/
   UNKNOWN with its source status, URL and retrieval date), a suggested next action, and a
   counterfactual search for the smallest single change that would flip a rejection. The rule-fit
   score (0–100) is a documented measure of how well the applicant fits the published criteria —
   **not** an approval probability — and never changes a gate or the ranking.

### Screening statuses (not bank approvals)

The engine screens published criteria; it does not issue sanctions, so no status says "approved":

| Status | Meaning |
|---|---|
| `ELIGIBLE_FOR_REQUESTED_TERMS` | passes all mandatory rules and covers the exact requested amount **and** tenure on published pricing |
| `ELIGIBLE_FOR_ALTERNATIVE_TERMS` | passes the rules, but only a smaller amount or shorter tenure fits; the alternative is shown separately |
| `PRELIMINARILY_ELIGIBLE` | passes the rules, but some terms are estimated/repriced, the rate is a range, the max rests on an estimated rule, or the card obligation is undetermined |
| `NOT_ELIGIBLE` | a documented mandatory rule is definitively violated |
| `ADDITIONAL_INFORMATION_REQUIRED` | a value needed to decide is missing (e.g. SE vintage/ITR, gender/profession for a specific product, an unavailable bureau score) |
| `MANUAL_REVIEW` | an ambiguous/unverified condition needs human interpretation (e.g. an estimated bureau signal) |
| `INVALID_INPUT` | the applicant data failed validation |
| `RULES_UNAVAILABLE` | insufficient rule data to make a defensible decision |

The best option is the lowest-APR eligible product that **covers the exact request**; offers whose
APR rests on an estimated rate are listed separately as *indicative*. The engine returns four
ranking categories (`rankings`): best-for-requested-terms, best-supported-alternative,
lowest-estimated-rate, lowest-reliable-APR, plus an insufficient-evidence flag. `GET /api/summary`
reports rule-base coverage and a per-product completeness count; these are coverage figures, not
approval rates.

### Canonical input contract

The Pydantic `Applicant` model is the single source of truth for input, shared by the backend and
mirrored in the frontend. It uses canonical field names (`existing_monthly_emi`, `card_outstanding`,
`card_monthly_payment`, `gross_monthly_income`, `salary_account_with`, `max_dpd_days_last_12_months`,
`enquiries_last_6_months`, `itr_years_available`, `has_settled_loan`, `settled_loan_months_ago`,
`write_off_flag`, `employer_check_off_available`, `verified_annual_income`) and accepts older names
as documented aliases. Any **other** unknown key is rejected, not silently dropped. Financially
material values that are missing stay *unknown* (`None`) — never coerced to 0 — so "no data" is
distinct from "zero". Age is computed in **completed calendar years** from `date_of_birth` and
`application_date` (born 1999-01-02 applying 2026-10-11 → 27, not 28), and the supplied application
date is preserved. Bureau state is explicit: valid score / new-to-credit / unavailable / failed /
invalid are kept distinct, and a required-but-unavailable score yields
`ADDITIONAL_INFORMATION_REQUIRED`.

#### Input variables (datapoint set)

As defined in `data/variables.csv` and enforced in `src/eligibility/schema.py`:

| Variable Name | Unit | Type | Origin | Description |
|---|---|---|---|---|
| `employment_type` | enum | Categorical | Applicant + Doc | `salaried`, `sep` (professional), or `seb` (business owner) |
| `employer_category` | enum | Categorical | Applicant + Doc | `govt`, `psu`, `defence`, `listed_mnc`, `private_large`, `private_small`, `other` |
| `profession` | enum | Categorical | Applicant + Doc | `doctor`, `ca`, `cs`, `cost_accountant`, `architect`, `engineer`, `consultant`, `other` |
| `date_of_birth` | YYYY-MM-DD | Date | Document | Applicant date of birth (used to compute exact calendar age) |
| `application_date` | YYYY-MM-DD | Date | System / App | Date of application (defaults to current date; preserved across runs) |
| `city` / `pincode` | text / 6-digit | String | Applicant | Resident city / pincode; mapped to Tier 1 / 2 / 3 via GoI HRA lookup |
| `net_monthly_income` | INR / month | Number | Document | Take-home salary after tax/PF (payslip or 6-month bank statement) |
| `gross_monthly_income` | INR / month | Number | Document | Total monthly salary before deductions (used by gross-FOIR lenders) |
| `total_experience_months`| Months | Integer | Applicant + Doc | Total cumulative working experience |
| `current_job_tenure_months`| Months | Integer | Applicant + Doc | Months with current employer / ongoing service |
| `business_vintage_months`| Months | Integer | Document | Months in continuous business/practice; required for SE segments |
| `itr_years_available` | Count | Integer | Document | Number of assessment years with filed Income Tax Returns |
| `itr_income_y1` | INR / year | Number | Document | Total income filed in most recent ITR year |
| `itr_income_y2` | INR / year | Number | Document | Total income filed in previous ITR year |
| `bureau_score` | 300–900 / None | Integer | Bureau | Credit bureau score (CIBIL / Experian); `None` indicates New-To-Credit |
| `credit_history_months` | Months / None | Integer | Bureau | Age of oldest reported tradeline on credit bureau |
| `existing_monthly_emi` | INR / month | Number | Bureau + App | Total active monthly loan EMIs being serviced |
| `credit_card_outstanding`| INR | Number | Bureau | Aggregate revolving credit card balances |
| `card_monthly_payment` | INR / month | Number | Applicant + Doc | Actual monthly card payment serviced (if unknown, 5% is NOT coerced) |
| `max_dpd_days_last_12_months` | Days | Integer | Bureau | Worst days-past-due delinquency across all tradelines in last 12m |
| `enquiries_last_6_months`| Count | Integer | Bureau | Count of hard credit enquiries in previous 6 months |
| `has_settled_loan` | Boolean | Boolean | Bureau | Whether any loan account reflects a "settled" status |
| `settled_loan_months_ago`| Months | Integer | Bureau | Months elapsed since the loan settlement occurred |
| `write_off_flag` | Boolean | Boolean | Bureau | Adverse credit marker indicating a loss/write-off |
| `salary_account_with` | Lender ID / None | Categorical | Applicant | Bank holding primary salary credit account |
| `employer_check_off_available` | Boolean | Boolean | Document | Employer salary deduction agreement available (PSU / corporate) |
| `requested_amount` | INR | Number | Applicant | Requested loan principal |
| `requested_tenure_months`| Months | Integer | Applicant | Requested repayment tenure in months |

*Feature derivations (such as FOIR headroom, age at loan maturity, and assessed income) are computed in `src/eligibility/preprocess.py`.*

## How the 20 lenders were chosen

The goal was the 20 that matter most to a real Indian borrower, under a defensible, reproducible
method (full detail in `model_report.md`):

1. **Start from system size** — PL market totals and origination mix from CRIF "How India Lends"
   and Experian (banks vs NBFCs vs digital lenders by value and volume).
2. **Rank lenders by personal-loan book / AUM** from company presentations and reputable secondary
   sources, filling gaps with retail-book scale and origination presence.
3. **Require three things of every lender:** a genuine unsecured personal-loan product, public
   eligibility information, and a national or large-regional footprint.
4. **Enforce a market-representative mix:** ≥5 PSU banks, ≥5 private banks, ≥4 NBFCs, and 2–3
   fintechs (which dominate origination *volume*).

### The 20 selected lenders

| Group | Lender Name | ID | Rules File | Primary Products Covered |
|---|---|---|---|---|
| **PSU Banks** | State Bank of India | `sbi` | `data/rules/sbi.csv` | Xpress Credit (Salary Package & Check-Off) |
| | Punjab National Bank | `pnb` | `data/rules/pnb.csv` | PNB Sahyog / Personal Loan Scheme |
| | Bank of Baroda | `bob` | `data/rules/bob.csv` | Baroda Personal Loan (Salaried & Professional) |
| | Canara Bank | `canara` | `data/rules/canara.csv` | Canara Budget Personal Loan |
| | Union Bank of India | `union` | `data/rules/union.csv` | Union Personal (Salaried & Professional schemes) |
| **Private Banks** | HDFC Bank | `hdfc` | `data/rules/hdfc.csv` | HDFC Personal Loan (Tiered by Employer Category) |
| | ICICI Bank | `icici` | `data/rules/icici.csv` | ICICI Personal Loan (Salaried & Self-Employed) |
| | Axis Bank | `axis` | `data/rules/axis.csv` | Axis 24x7 Personal Loan |
| | Kotak Mahindra Bank | `kotak` | `data/rules/kotak.csv` | Kotak Personal Loan (Salaried) |
| | IndusInd Bank | `indusind` | `data/rules/indusind.csv` | IndusInd Multi-Purpose Personal Loan |
| | IDFC FIRST Bank | `idfc` | `data/rules/idfc_first.csv` | IDFC FIRST Personal Loan |
| | YES Bank | `yes` | `data/rules/yes.csv` | YES Bank Personal Loan |
| **NBFCs** | Bajaj Finance | `bajaj` | `data/rules/bajaj.csv` | Bajaj Finserv Flexi Personal Loan |
| | Tata Capital | `tata` | `data/rules/tata_capital.csv` | Tata Capital Personal Loan (Salaried & Business) |
| | Aditya Birla Capital | `aditya_birla` | `data/rules/aditya_birla.csv` | ABFL Personal Loan |
| | L&T Finance | `lnt` | `data/rules/lt_finance.csv` | L&T Consumer Loan |
| | Poonawalla Fincorp | `poonawalla` | `data/rules/poonawalla.csv` | Poonawalla Personal Loan |
| **Fintechs** | Navi Technologies | `navi` | `data/rules/navi.csv` | Navi Cash Loan (Digital unsecured PL) |
| | KreditBee | `kreditbee` | `data/rules/kreditbee.csv` | KreditBee Personal Loan for Salaried / Flexi |
| | Moneyview | `moneyview` | `data/rules/moneyview.csv` | Moneyview Personal Loan |

All individual lender rules live as atomic rows in `data/rules/{lender}.csv`, compiled into `data/lender_rules_long.csv` (1,260 rules). Every published rule is backed by a dated snapshot in `data/sources/`.

## Approach

- **Rules as data, engine as code.** Every lender rule lives in `data/rules/{lender}.csv` as an
  atomic row (variable, operator, value, condition, source URL, retrieval date, confidence,
  verbatim quote). The engine is a generic evaluator over that table — adding or correcting a lender
  is a data edit, not a code change.
- **Provenance on every rule.** Each row is tagged by confidence
  (`VERIFIED_PUBLISHED` / `DERIVED_FROM_PUBLIC_CALCULATOR` / `INFERRED` / `ESTIMATED` /
  `CONFLICT_REQUIRES_REVIEW` / `UNKNOWN`), and published rows carry a quote that must be an exact
  substring of a saved, dated page snapshot in `data/sources/`. `scripts/verify_rules.py` enforces
  this, so the engine cannot silently drift from the sources.
- **Conflict policy:** where a lender's own pages disagree, the engine uses the **stricter** value
  and keeps the alternative in `data/conflicts.csv`.
- **Reproducibility & change detection.** Each decision records a `rule_set_version` (content hash
  of the rule table). `scripts/check_source_drift.py` hashes every snapshot into a manifest and
  writes a review queue on drift — a changed page is never auto-accepted as a verified rule.
  `scripts/audit_generic_defaults.py` lists every non-published material rule, so no lender is shown
  as fully verified when its material rules are assumptions.

## Assumptions, and how unlisted rules were found

**Finding rules lenders don't publish.** ICICI and Kotak expose public eligibility *calculators*
that output a maximum loan for a given income and obligations. Each was probed on a grid of inputs,
~20% held out, and the hidden sizing formula least-squares-fitted:

- **Kotak:** `max_loan ≈ 20 × (net income − existing EMI)`, tenure-independent.
- **ICICI:** FOIR ≈ 70%, capitalised by an annuity factor ≈ 46.57, capped at ₹50L.

Both reproduce the held-out outputs at **< 0.5% mean error** (`tests/test_phase4_affordability.py`
replays every probe). These are tagged `derived`, not published.

**Where a value isn't knowable from public sources it is an explicit assumption** (tagged
`estimated`, never `published`):

- **Bureau hygiene** (DPD / enquiries / settlements) — a tiered policy. A write-off (a documented
  adverse marker) hard-rejects at banks and strict NBFCs. The estimated, unpublished thresholds
  (recent DPD, 6+ enquiries, a prior settlement) route to `MANUAL_REVIEW` rather than a fabricated
  rejection; NBFCs/fintechs reprice within the published band.
- **FOIR / income-multiple** for lenders that publish neither (default FOIR 60%, multiple ≤ 20×),
  used only when no published or calibrated value exists, and flagged where it binds the max.
- **Income reading:** gross-FOIR banks (BoB/PNB/Canara) use the supplied `gross_monthly_income`;
  when only net is given, a `net / 0.75` estimate is used but flagged `GROSS_INCOME_ESTIMATED`, with
  the affordability caps computed on net so the max is not inflated.
- **Card obligation:** the supplied `card_monthly_payment` is used; an unknown payment on a positive
  balance is never imputed (`CARD_PAYMENT_UNKNOWN`), and the affordability-based max is marked
  indicative.
- **Rate within a published band** is placed by score band; when the applicant's exact rate is
  unknown the band is returned as a range and the APR is marked indicative.

## Insights

From a seeded synthetic population of 3,000 applicants (`eligibility.simulate`, reproducible with
`seed=42`) run through the engine — 60,000 lender/applicant evaluations:

- **The credit score is the single biggest gate.** Of all `NOT_ELIGIBLE` outcomes, the primary
  reason is `SCORE_BELOW_MIN` ~19% of the time, ahead of `SEGMENT_NOT_OFFERED` (~16%),
  `NTC_NOT_ALLOWED` (~13%) and `EMPLOYER_NOT_ALLOWED` (~12%).
- **Lenders differ enormously in reach.** Fintechs match the widest slice; the strictest bank
  products (check-off / listed-profession) match a small fraction. A typical applicant matches
  roughly a third of the 20 lenders.
- **What binds the loan size changes with the borrower.** For thin-income applicants FOIR or the
  take-home floor binds; for high earners the product cap binds. The engine records
  `caps.binding_cap` on every offer, so this is visible, not guessed.
- **The lowest headline rate is often not the lowest APR** once the processing fee + GST are
  included — which is why ranking is by APR, not advertised rate.

## Limits

- Internal scorecards, employer allow-lists, and document checks are invisible to any outside model;
  the engine screens *published* criteria and never asserts a bank sanction.
- Rule completeness varies by product: of 34 products, 21 are *complete* (published gate + sizing +
  pricing + fee) and 13 are *partial* — reported by `/api/completeness`. No lender is presented as
  fully verified when a material rule is only estimated.
- Some FOIR/multiple and bureau-hygiene thresholds are estimated (flagged as such); where a product's
  max rests on an estimated rule (e.g. parts of Union's professional schemes, whose live pages render
  only tab headings), the offer is `PRELIMINARILY_ELIGIBLE` with the max marked indicative.
- Fintech pricing is personalised, so those APRs are wide, low-confidence ranges.
- Regulatory scope: this is a non-transacting comparison/estimation tool, so it is not itself a
  Regulated Entity / LSP under the RBI Digital Lending Directions, 2025. It nonetheless adopts the
  Key Facts Statement design objectives (APR as an IRR on net cash flows, costs shown separately,
  published vs estimated distinguished, no approval claims). This is a design conclusion, not legal
  advice.
- The synthetic population uses assumed marginals; its shares are illustrative, not official.
- Rules change constantly — every value is dated, and snapshots will go stale.

## Repository layout

```
data/
  sources/              dated snapshots of lender pages + PDF text extractions
  rules/{lender}.csv    per-lender atomic rules (source of truth)
  lender_rules_long.csv merged rule table (1,260 rules) consumed by the engine
  conflicts.csv         variables where a lender's own pages disagree + the value used
  lookups/              city->tier, employer->category, profession allow-lists, rate grids
  calibration/          calculator probes + fitted parameters (ICICI, Kotak)
  variables.csv         the feature catalogue + coverage counts
src/eligibility/
  schema.py             Pydantic applicant / rule / decision models
  conditions.py         parser for the free-text rule conditions
  rules.py              rule store (load + index + condition pre-parse + version hash)
  lookups.py            city / employer / profession resolution
  preprocess.py         derived features
  finance.py            EMI, PV annuity (reducing balance)
  calibration.py        fitted ICICI/Kotak calculator models
  affordability.py      loan sizing + binding-cap tracking
  pricing.py            rate band, fee+GST, APR by IRR, dated fee waivers, repricing
  strength.py           rule-fit scorecard (documented weights; not approval odds)
  gates.py              hard-gate evaluation + decision trace + tiered bureau policy
  engine.py             orchestration across all 20 lenders + ranking
  counterfactual.py     minimal verified "how to qualify" advice
  simulate.py           synthetic population + sensitivity
  quality.py            rule-base coverage + per-product completeness report
  cli.py / __main__.py  command-line interface
  api.py                FastAPI HTTP API
scripts/                rule-table build, calibration fit, source snapshot + drift, audits
frontend/               Vite + React + TypeScript UI (form -> 20-lender table + reasons/advice)
tests/                  phase gates, sample profiles, golden baselines, regression + API tests
```

## Frontend + backend

The UI is a React (Vite + TypeScript) single page that calls the FastAPI backend:

- Start the API: `uvicorn eligibility.api:app --port 8000`
- Start the UI: `cd frontend && npm install && npm run dev`

In development the Vite server proxies `/api/*` to `http://127.0.0.1:8000`, so the browser sees a
single origin. The form has a **"Paste JSON / load a sample profile"** box that auto-fills every
field from a pasted payload or a bundled profile; unsupported keys are reported, not dropped, and
dates are preserved exactly. `npm run build` emits static files in `frontend/dist/` for any static
host.

## Testing

`pytest` runs the backend suite (357 tests): data contracts, the condition parser over all real
conditions, boundary tests per gate, Hypothesis property tests, the **calibration replay** (every
ICICI/Kotak probe reproduced within tolerance), the golden profiles, the regression profiles (one
per observed defect), consistency verifications with **independently computed** EMI/APR/age
reference values, dated fee-waiver checks, rule-confidence/completeness checks, and the FastAPI
endpoints. `cd frontend && npm test` runs the frontend input-mapping suite that proves every
sample-profile field survives the JSON → form → backend-payload path unchanged, with no
zero-filling, plus a frontend/backend consistency check across the regression profiles.

### Test profiles & sample outputs

The engine is evaluated against 16 bundled baseline profiles (`tests/profiles/P01.json` – `P16.json`)
and 10 dedicated edge profiles (`tests/edge_profiles/EDGE01.json` – `EDGE10.json`).

Run all bundled sample profiles through the engine:
```powershell
python scripts/run_profiles.py
```

| Profile | Scenario / Persona | Key Characteristics | Status | Best-Fit Lender | Key Decision Insight |
|---|---|---|---|---|---|
| **P01** | Prime Salaried | Metro, MNC Cat A, ₹1.2L salary, score 785 | Eligible (18/20) | IDFC FIRST (9.99% APR) | Broad eligibility; binding cap is product maximum or salary multiple. |
| **P02** | Subprime / Adverse bureau | Score 640, DPD 30 in 12m, 8 enquiries | Eligible (2/20) | KreditBee (29.98% APR) | Banks reject or route to manual review; digital fintechs approve at repriced risk rates. |
| **P03** | High existing EMI | Net ₹1L/mo, existing EMI ₹55K (55% FOIR) | Eligible (13/20) | ICICI Bank (12.34% APR) | Strict FOIR cap binds loan sizing; ICICI calculator model covers requested amount. |
| **P04** | Job Hopper / Low tenure | Current job 4 months, total 36m | Eligible (11/20) | IDFC FIRST (12.79% APR) | Banks requiring 6–12m with current employer reject (`EXP_CURRENT_LT_MIN`). |
| **P05** | Young Fresher / NTC | Age 21, 8m exp, New-To-Credit (no score) | Ineligible (0/20) | None | Blocked across all lenders by `AGE_BELOW_MIN`, `EXP_TOTAL_LT_MIN`, and `NTC_NOT_ALLOWED`. |
| **P06** | Near-Retirement Senior | Age 57, requests 60m tenure | Eligible (17/20) | Canara Bank (11.11% APR) | Age-at-maturity cap (60 years) curtails allowed tenure to 36m (`ELIGIBLE_FOR_ALTERNATIVE_TERMS`). |
| **P07** | Self-Employed Doctor (SEP) | Doctor, ₹1.5L/mo, clinic vintage 48m | Eligible (11/20) | IDFC FIRST (12.79% APR) | Qualifies for specialized professional schemes; high loan multiple permitted. |
| **P08** | Self-Employed Business (SEB) | 2yr vintage, 1 ITR year, ₹1.2L/mo | Eligible (9/20) | KreditBee (20.12% APR) | Banks requiring $\ge 2$ or 3 years of filed ITRs reject (`ITR_YEARS_LT_MIN`); NBFCs/fintechs approve. |
| **P09** | Pure New-To-Credit (NTC) | Age 29, salary ₹45K, no credit score | Eligible (2/20) | Poonawalla (25.29% APR) | Traditional score-gated banks reject; NTC-friendly NBFCs approve. |
| **P10** | Recent Delinquency | Score 720, DPD 60 in last 12m | Eligible (16/20) | Navi (24.81% APR) | Bank products trigger `MANUAL_REVIEW` under tiered bureau hygiene; fintechs approve with risk repricing. |
| **P11** | Credit Hungry / Enquiries | 9 enquiries in last 6m, score 735 | Eligible (15/20) | L&T Finance (22.35% APR) | Enquiries trigger review at banks; NBFCs absorb the applicant at standard risk bands. |
| **P12** | Tier-3 Low Income | Tier-3 city, salary ₹18K/mo | Eligible (6/20) | Canara Bank (12.50% APR) | Metro-only floors (₹25K–₹30K) reject; PSU tier-adjusted income floor admits the applicant. |
| **P13** | Ultra High Net Worth | Salary ₹4.5L/mo, requests ₹50 Lakhs | Eligible (18/20) | Canara Bank (9.75% APR) | Product ceiling (₹40L–₹50L) binds instead of FOIR. |
| **P14** | Government Employee | Govt teacher, SBI salary account, check-off | Eligible (17/20) | SBI (11.65% APR) | Unlocks SBI Xpress Credit check-off terms with discounted interest rate. |
| **P15** | Boundary Test / Exact Minimums | Age 21, ₹15K salary, Tier 3, score 650 | Eligible (1/20) | IDFC FIRST (16.29% APR) | Tests exact mathematical boundary gates across all rule operators ($\ge$ vs $>$). |
| **P16** | Prior Loan Settlement | Settlement 18 months ago, score 690 | Eligible (1/20) | KreditBee (29.98% APR) | Strict banks reject on settlement history (`PRIOR_SETTLEMENT`); fintech flexi products admit. |

See `model_report.md` for the full design, the feature catalogue, the calibration method, and the
worked examples. Every estimated value is flagged and surfaced in the UI; no result is a loan offer.

