# Personal Loan Eligibility Model — Design Report (model_report.md)

**Role:** Senior Data Scientist, fintech MNC. **Date:** 2026-10-10. **Status:** Design + v0.1 rule table + computed sample outputs. **Model code: NOT yet built** (per instruction — this document is the build spec).
**Task source:** `Personal loan eligibility model.md` (placement task — personal loans only, top-20 lenders, public sources only, no ML, rule-based/scorecard + 10+ test profiles + README).
**Prior-company material:** the NBFC/IBL folder was used for *methodology only* (leakage discipline, NULL-vs-zero handling, bureau-field knowledge, reason-code explanations). No IBL schema, data, docs, or customer PII is reproduced here or will go into the repo.

---

## Addendum — production-grade upgrade (2026-10-11)

The engine has since been built and hardened against a detailed audit (`prompts/plan2.md`). The
sections below are the original design spec; this addendum records what changed in the shipped code,
and takes precedence where they differ:

- **Canonical input contract.** The Pydantic `Applicant` is the single source of truth, using the
  canonical field names `existing_monthly_emi`, `card_outstanding`, `salary_account_with`,
  `max_dpd_days_last_12_months`, `enquiries_last_6_months`, `itr_years_available`, `has_settled_loan`,
  `settled_loan_months_ago`, `write_off_flag` (legacy names accepted as documented aliases; other
  unknown keys rejected). Missing material values stay `None`, never 0; bureau state (valid / NTC /
  unavailable / failed / invalid) is explicit; age is completed calendar years from DOB + application
  date, with the application date preserved.
- **Decision statuses** replace the old APPROVE/REDUCED shorthand with:
  `ELIGIBLE_FOR_REQUESTED_TERMS`, `ELIGIBLE_FOR_ALTERNATIVE_TERMS`, `PRELIMINARILY_ELIGIBLE`,
  `NOT_ELIGIBLE`, `ADDITIONAL_INFORMATION_REQUIRED`, `MANUAL_REVIEW`, `INVALID_INPUT`,
  `RULES_UNAVAILABLE`. The requested amount/tenure are never rewritten; a reduced offer is a separate
  `alternative` quote, not a sanction.
- **Separate quotes.** `requested`, `alternative` and `max_eligible` each carry their own
  (amount, tenure, EMI); EMIs are never mixed, and each is labelled with its principal/rate/tenure.
- **Product caps** are bounded even when `loan_max` is variant-conditional (fixing the Canara ₹1.52 Cr
  runaway → capped at the published ₹50L); "selectively higher" amounts are flagged, never applied;
  an estimated-only sizing rule demotes the offer to `PRELIMINARILY_ELIGIBLE` with the max marked
  indicative.
- **Pricing/APR** is an IRR on net-of-fee cash flows (RBI Key Facts Statement method), with rate /
  fee / GST / net disbursal / totals kept separate; time-bound fee waivers apply only inside their
  effective window.
- **Confidence taxonomy** (`VERIFIED_PUBLISHED` / `CONFLICT_REQUIRES_REVIEW` / `INFERRED` /
  `ESTIMATED` / `UNKNOWN`) and a per-product completeness report (21 complete / 13 partial / 0
  insufficient of 34) are exposed via `/api/summary` and `/api/completeness`.
- **The "strength score" is redefined** as a documented rule-fit / data-completeness score (0–100),
  explicitly *not* an approval probability, and excluded from ranking. Ranking is by APR (then EMI)
  over offers that cover the exact request; estimated-APR offers are listed as indicative.
- **Tests:** 296 backend (pytest) incl. one regression per observed defect (A–J), the 25 required
  consistency checks with independent reference values, dated-waiver and completeness checks; plus 10
  frontend vitest input-mapping tests. Rule table is now 1,260 rows (added YES's published ₹50L cap).

---

## Table of contents

1. Executive summary
2. Scope, constraints, definitions
3. Lender selection — the final 20 and how they were chosen
4. Data sources and collection instructions
5. How unlisted rules are found (calculator reverse-engineering)
6. Feature catalogue — 34 features (why chosen / how chosen / how engineered)
7. Data preprocessing — exact instructions
8. Model architecture — gates, sizing, pricing, best-option, scorecard
9. Training process — calibration, NOT ML (step-by-step instructions)
10. Synthetic population for insights (never for training)
11. Testing — unit, property, golden-output, data-quality, calculator-accuracy
12. Sample profiles P01–P16 with computed outputs
13. Insights from v0.1 (preliminary), limitations, next steps
14. Run instructions and repo contract
15. Appendix A — reason-code dictionary
16. Appendix B — v0.1 rule table (values, sources, confidence, dates)
17. Appendix C — glossary + key sources

---

## 1. Executive summary

**Question:** "Can I get a personal loan, and from whom?" — for one Indian applicant profile, across the top 20 personal-loan lenders.

**Answer this design gives:** a deterministic rule engine + pricing scorecard. For each lender it returns APPROVE / APPROVE_REDUCED / REJECT with reason codes, max loan amount, expected rate, available tenures and APR including fees. Overall verdict = eligible if ≥1 lender approves. Best option = lowest APR for the requested amount, with a generated explanation. Every rejection carries the smallest actionable fix ("close ₹X EMI", "wait N months", "extend tenure").

**Why not ML:** the brief forbids it ("Do not train an ML model, because there is no approval data") and it would be wrong anyway — we have no approval labels, and synthetic labels would only teach the model our own assumptions. The "training process" in §9 is therefore **calibration**: fitting FOIR caps, income multiples and age caps from lenders' own calculators, setting scorecard weights from underwriting judgement, and validating on held-out calculator probes.

**What was actually done for this report (2026-10-09/10):** (a) lender ranking from CRIF/FACE/company data; (b) public-rule research for all 20 lenders (official pages first, aggregators only to triangulate; every value carries source URL + access date + confidence); (c) a 34-feature catalogue; (d) a **throwaway** calc script (temp folder, deleted after use — not the model) to compute EMI/APR/max-loan maths without arithmetic errors; (e) 16 sample profiles with computed outputs in §12.

**Headline results (engine-computed, §12):** prime profile P01 is approved by 18/20 lenders (best Union, APR 9.25%). Bureau-driven profiles show the tiered policy at work: low-score P02 and settled-loan P16 drop to a single lenient-fintech offer, DPD-60 P10 gets three repriced NBFC/fintech offers, and enquiry-heavy P11 gets seven. High-EMI P03 is mostly reduced, with Canara's take-home-floor rule giving the most room. New-job P04 fails the lenders with a 12-month current-job rule. New-to-credit P09 passes only where an NTC policy is published. High-earner P13 is bound by product caps, not multiples. Every figure is reproducible via `python -m eligibility evaluate tests/profiles/P01.json`.

---

## 2. Scope, constraints, definitions

- **Personal loans only.** Unsecured, general-purpose. Excludes gold, home, auto, LAP, business loans, professional loans. Where a lender books self-employed "personal loans" as business-instalment loans (ICICI), that is noted and kept only if the lender markets it as a personal loan.
- **Top 20 lenders** chosen by evidence (§3). Mix: 12 banks (6 PSU + 6 private), 5 NBFCs, 3 fintechs. Separate rule sets for **salaried** vs **self-employed professional (SEP)** vs **self-employed business (SEB)**.
- **Public sources only.** No customer data, no login/OTP pages. Every rule value: `source_url + accessed_date + confidence (published / derived / estimated) + estimation_method`.
- **Current rules.** All sources read 2026-10-09/10. Rates move with repo/MCLR/EBLR — the rule table stores the *spread/margin method* plus the benchmark value and date, not just a headline rate.
- **No ML.** Rule engine + scorecard. Approval-strength score 0–100 uses published weights (never trained, never overrides a hard gate).
- **Definitions:** FOIR = (existing obligations + new EMI)/assessed income. NMI = net monthly income. DPD = days past due. APR = IRR on net disbursed amount (loan minus processing fee minus 18% GST) against the EMI stream — the RBI Key Facts Statement method. NTC = new-to-credit (no bureau score, `bureau_score = NULL`).

---

## 3. Lender selection — the final 20 and how they were chosen

### 3.1 Method (reproducible)

1. Start from system totals: CRIF "How India Lends" Sep-2026 — PL outstanding ~₹17.0 lakh cr (+13.8% YoY, Jun-2026); Experian ~₹16.2 lakh cr. Originations Q1 FY27 ~₹3.19 lakh cr / ~490 lakh loans; by value NBFC 46.0%, private banks 27.0%, PSU banks 22.8%; by volume NBFC 92.3% (CRIF). Digital NBFCs: ~70% of sanction volume, ~22% of value, avg ticket ~₹18.8k vs banks ~₹4.52L (FACE Q1 FY27).
2. Collect lender-level PL books/AUM from company presentations and reputable secondaries (IDBI Capital Q1FY27 notes for HDFC/ICICI/Axis; Bajaj Finserv Q1FY27 deck; Mint/ET for Navi/KreditBee/Moneyview/Fibe; Piramal deck).
3. Rank by PL book where published; fill gaps by retail-book scale + origination presence. Require: a genuine unsecured personal-loan product, public eligibility info, national or large-regional footprint.
4. Enforce mix constraints: ≥5 PSU, ≥5 private, ≥4 NBFC, 2–3 fintech (brief explicitly allows fintechs). Document near-misses.

### 3.2 Published size evidence (best available, mixed metrics — do not compare naively)

| Lender | Metric | Value | As-of | Source |
|---|---|---|---|---|
| SBI | Xpress Credit book | ₹3,76,000 cr | Mar-2026 | NDTV Profit quoting SBI annual report |
| HDFC Bank | PL book | ₹2,22,400 cr | Jun-2026 | IDBI Capital Q1FY27 note |
| Bajaj Finance | Urban+Rural PL AUM | ₹1,37,031 cr | Jun-2026 | Bajaj Finserv Q1FY27 investor deck p.54 |
| ICICI Bank | PL book | ₹1,35,520 cr | Jun-2026 | IDBI Capital Q1FY27 note |
| Axis Bank | PL book | ₹82,781 cr | Jun-2026 | IDBI Capital Q1FY27 note |
| Kotak | Unsecured retail ~8.8% of advances (~₹45,000 cr incl. cards/MFI, derived) | — | Jun-2026 | ICICI Direct Q1FY27 + advances base |
| Tata Capital | Personal-or-business AUM ₹26,202 cr (PL subset) | Jun-2026 | HDFC Sky/Q1 report | — |
| Moneyview | Managed AUM ₹22,520 cr (mostly partner-book, do not rank vs bank books) | Jun-2026 | PTI/MSN pre-IPO | — |
| KreditBee | AUM ~₹14,700 cr (forecast) | FY26 | Mint / IBS Intelligence | — |
| Navi Finserv | Loan book ~₹13,000 cr (PL ~90%) | Mar-2026 | Mint | — |
| Fibe | PL AUM ₹6,657 cr | Mar-2026 | ETCFO/DRHP | — |
| Piramal | Salaried PL AUM ₹8,381 cr | Jun-2026 | Piramal Q1FY27 deck | — |

PSU banks below SBI (BoB, PNB, Canara, Union) do not publish clean PL splits; they are included on retail scale (e.g. BoB domestic retail ~₹3.10 lakh cr) + origination presence. Their order among themselves is alphabetical, not a size claim.

### 3.3 Final 20 (IDs used in this report)

| ID | Lender | Type | Why included |
|---|---|---|---|
| L01 | SBI | PSU | Largest PL book; publishes the most complete rules incl. FOIR 65%, 30× multiple |
| L02 | HDFC Bank | Private | #2 PL book; benchmark private lender |
| L03 | ICICI Bank | Private | #3 bank PL book; offers self-employed track |
| L04 | Axis Bank | Private | Top-5 PL book; publishes tier-wise city list |
| L05 | Kotak Mahindra | Private | Large unsecured retail; ₹1 cr max ticket |
| L06 | Bank of Baroda | PSU | Large PSU retail; rare published FOIR grid (40–75% of GMI by employer tier) |
| L07 | PNB | PSU | Large PSU; publishes score-band rate grid incl. NTC pricing |
| L08 | Canara Bank | PSU | Large PSU; publishes take-home-floor rule + CRG rate grid |
| L09 | Union Bank of India | PSU | Only bank with full EBLR+spread score grid; NTC priced |
| L10 | IndusInd Bank | Private | Mid private; publishes 730 score floor + exp rules |
| L11 | IDFC FIRST Bank | Private | Digital-first bank; two tracks (FIRSTmoney + higher-limit) |
| L12 | Yes Bank | Private | Mid private; complete published gates |
| L13 | Bajaj Finance | NBFC | Largest NBFC PL book (≈ next 9 NBFCs combined per Nomura/ET) |
| L14 | Tata Capital | NBFC | Large NBFC; publishes FOIR/multiple guidance |
| L15 | Aditya Birla Capital | NBFC | Large NBFC; publishes city-tier income grid + 28% policy cap |
| L16 | L&T Finance | NBFC | Large retail book; publishes interest-rate-model PDF (10.50–24%) |
| L17 | Poonawalla Fincorp | NBFC | Listed NBFC; 3 PL variants incl. Prime + Instant |
| L18 | Navi Finserv | Fintech NBFC | Own-book fintech; zero-foreclosure; co-lending with Tata Capital |
| L19 | KreditBee | Fintech platform | Accepts low-score + NTC; publishes APR range + worked KFS-style example |
| L20 | Moneyview | Fintech platform | 16 lending partners; publishes monthly-rate + APR ranges |

**Near-misses (documented, excluded):** Bank of India / Indian Bank / Bank of Maharashtra (no clean PL product pages found in research window); Federal / RBL / IDBI (smaller PL presence); Hero FinCorp / Fibe / Piramal / SMFG / Chola (smaller PL AUM than chosen fintechs/NBFCs or overlapping segments). Revisit if book data appears.

---

## 4. Data sources and collection instructions

**Source priority (conflicts resolved top-down):** (1) official eligibility / rates / fees / MITC / interest-rate-policy PDF / KFS sample; (2) values derived from the lender's own calculator by controlled probes (§5); (3) quarterly actual-rate disclosures (min/max/mean where published — HDFC, ICICI, Axis, Union, Canara); (4) aggregators (Paisabazaar/BankBazaar) for triangulation only; (5) industry-norm defaults, always lowest confidence.

**Collector instructions (must be followed for the repo `data/` build):**
1. Fetch official pages with `webfetch` (text). If 404 (e.g. old Bajaj eligibility URL), `web_search` the current URL. If JS-only (Navi product pages), record search-snippet text as `published (snippet, unverified)` and prefer the readable T&C page.
2. Save a raw snapshot per source into `data/sources/{lender}_{page}_{YYYY-MM-DD}.md` with URL + access date. Never edit snapshots.
3. Record each atomic rule as one row in `lender_rules_long.csv`: `lender, segment, variable, operator, value, unit, effect, condition, source_url, accessed_date, confidence, estimation_method, quote`.
4. Quote ≤25-word exact phrases for key numbers. Log every conflict (both values, both sources) in `data/conflicts.csv` — do not silently pick one; the engine uses the documented resolution in Appendix B.
5. RBI context to record alongside: risk weight on unsecured consumer credit raised 100%→125% (Nov-2023, banks 150%/NBFCs 125% per later clarifications — cite Moneycontrol/CNBC-TV18 summaries); repo 5.50% with EBLR ≈ 8.00–8.35% in Sep–Oct 2026 (Union PDF, PNB RLLR page). These explain why floating-rate grids move.

---

## 5. How unlisted rules are found (calculator reverse-engineering)

FOIR caps, income multiples and age-at-maturity caps are rarely published (only SBI 65%/30×, BoB FOIR grid, Canara take-home floor, Tata 40–50%/9–18× guidance, Bajaj/L&T generic 50–60%/10–18× text). The method:

1. **Probe grid.** Drive each lender's eligibility/EMI calculator (Playwright where JS is required; skip login/OTP calculators) over controlled inputs: vary income holding EMI/age/tenure fixed; vary existing EMI; vary age; vary tenure.
2. **Solve backwards.** (a) `FOIR = (EMI_of_returned_max_loan + existing_EMI)/income` at each income → flat line = single cap, kink = income bands. (b) Rupee-for-rupee EMI subtraction test → reveals card/outstanding treatment. (c) Tenure cliff as age rises → `max_age_at_maturity`. (d) Tenure sweep at fixed income → implied pricing rate.
3. **Cross-check** against KFS samples / quarterly actual-rate ranges / aggregator bands.
4. **Hold out 20% of probe points** for the calculator-accuracy test (§11.5). Solved rules are `derived`; unsolved ones stay `estimated` with the default in Appendix B and enter sensitivity analysis.
5. **Status for this report:** full Playwright probing is *not yet run* (model build phase). v0.1 FOIR/multiples below are `estimated` defaults (banks 0.60, BoB 0.70 per its grid, SBI 0.65 published, Canara 0.75 per take-home floor, Tata 0.50, L&T 0.55; multiples 12–30 per Appendix B) — each flagged as such and sensitivity-tested in the build phase.

---

## 6. Feature catalogue — 34 features

**Selection method (so the count is auditable):** every lender rule was atomised (§4.3); a lender×variable coverage matrix was built; a candidate became a model input only if (i) ≥1 rule uses it or a rule needs it to compute, (ii) it is knowable at application time (applicant/bureau/document — nothing post-disbursal; the IBL leakage rule, adapted), (iii) it has one standard definition + unit, (iv) it is fair-lending safe (no religion/caste/pincode; pincode → city-tier lookup only; gender excluded — no lender publishes a gender rule). Overlapping candidates were merged; display-only fields (requested_amount, per-offer outputs) are excluded from the count. Result: **22 raw + 12 derived = 34**.

> **Coverage counts (data-driven):** the "n/20" figures in the table below are computed from `data/lender_rules_long.csv` by `scripts/build_variables.py` into `data/coverage_matrix.csv` and `data/variables.csv`. Each cell counts lenders with at least one published-or-derived rule reading that feature; bureau features (F15–F17) are applied to every lender via the tiered policy and so show their published-rule count, not 20.

**Origin key:** A = applicant declares, B = bureau, D = document-verified, S = system.

| # | Feature | Unit / type | Origin | Why chosen (rules that need it) | How chosen (coverage) | How engineered (formula, nulls, edges) |
|---|---|---|---|---|---|---|
| F01 | employment_type | enum salaried/SEP/SEB | A+D | Chooses the entire rule set; 6/20 lenders offer no SE track | 20/20 rules branch on it | Standardised 3-way enum; SEP = doctor/CA/architect etc., SEB = all other self-employed; validated against profession+vintage |
| F02 | employer_category | enum govt/PSU/defence/listed-MNC/private-large/private-small/other | A+D | SBI/BoB/Canara/PNB/Union rate+FOIR+tenure tiers key off it | 12/20 use it in gates or pricing | Map employer name → tier per lender mapping table; unknown → private-small (conservative); stored per-lender (`employer_tier_L`) |
| F03 | profession | enum (doctor/CA/CS/architect/engineer/consultant/other) | A+D | PNB-SE allow-list; Union-Professional allow-list; BoB professional list | 5/20 gate on it | Allow-list match per lender; non-listed professional → SEB track |
| F04 | total_experience_months | months, int ≥0 | A+D | HDFC 24m, ICICI 24m, Axis ~12m(doc), Tata 24m, Poonawalla 12m/6m gates | 14/20 | max(0, application_date − career_start); payslip/EPFO cross-check flag; students/FTE interns excluded |
| F05 | current_job_tenure_months | months, int ≥0 | A+D (payslips) | HDFC 12m-current, IndusInd 12m, Kotak unlisted, Poonawalla 1m gates | 11/20 | months since DOJ; probation flag if <6m (Bajaj lists probation as reject signal) |
| F06 | business_vintage_months | months, int; NULL for salaried | D (GST/registration) | ICICI-SE 24m current, Tata unlisted, L&T 24m, Poonawalla-Prof 12m post-qualification | 9/20 (SE tracks) | NULL for salaried (never 0); registration/GST date; <12m → most SE tracks reject |
| F07 | net_monthly_income | ₹/month, >0 | D (payslip/bank stmt) | Every lender's income gate + FOIR + multiple denominator | 20/20 | Take-home after tax+PF (ABCL explicitly uses take-home, not CTC); outlier clip ₹8k–₹50L with flag; city-tier minimum applied per lender |
| F08 | itr_income_y1 | ₹/year, NULL for salaried | D (ITR) | SE income assessment (latest year) | 8/20 SE tracks | Latest filed ITR total income; NULL for salaried |
| F09 | itr_income_y2 | ₹/year, NULL | D (ITR) | 2-yr average / growth check | 6/20 SE tracks | Year-before-last; NULL if <2 ITRs filed |
| F10 | itr_years_filed | count 0–10 | D | PNB-SE 2yrs, Union-Prof 3yrs, L&T 2 consecutive, Tata 2yr financials | 7/20 | Count of AYs with filed ITR; <2 → most SE tracks reject |
| F11 | existing_emi_monthly | ₹/month, ≥0 | B | FOIR numerator everywhere; SBI EMI/NMI 65%, BoB 40–75% GMI | 20/20 | Sum of bureau active-EMI obligations; EMIs ending within lender's exclusion window (usually 6m, estimated) subtracted; NULL→0 only here (no loans = zero obligation is correct) |
| F12 | credit_card_outstanding | ₹, ≥0 | B | Assumed monthly obligation = k×outstanding (k≈5%, estimated) | 8/20 explicit, rest implicit | Bureau revolving outstanding; monthly load = 0.05×outstanding; documented as estimated |
| F13 | bureau_score | 300–900 or NULL | B | Score gates (HDFC 720, IDFC 710/730, IndusInd 730, Bajaj 650, L&T 700, ABCL 700, Yes 700, SBI 650/670, PNB-SE 750, Moneyview/KreditBee 650/none) + all rate bands | 20/20 | Max of CIBIL/Experian if both; NULL = NTC (never 0 — the IBL NULL rule); bureau pull date must be ≤ application date |
| F14 | credit_history_months | months or NULL | B | Thin-file detection; complements score | 6/20 explicit | Oldest trade age; NULL if no trades; <12m = thin file (rate loading, some lenders reject) |
| F15 | max_dpd_last_12m | days 0–180 or NULL | B | Unlisted delinquency gate (estimated ≥30 reject); Bajaj lists settlements/write-offs as reject | ~20/20 (estimated) | Decode bureau 48-month strings via canonical map (000/STD/NEW/CLSD=0, 030/060/090…=face, `*`=NULL); NULL if no history |
| F16 | enquiries_last_6m | count ≥0 | B | Unlisted credit-hunger gate (estimated ≥6 reject) | ~20/20 (estimated) | Bureau enquiry count 6m window; 0 allowed |
| F17 | writeoff_or_settled_24m | bool | B | Hard reject (estimated; Bajaj published as reject signal) | ~20/20 (estimated) | Any write-off/settlement flag 24m; TRUE → reject at all lenders in v0.1 |
| F18 | active_unsecured_loans | count ≥0 | B | Stacking limit (estimated ≥4 flag) | 4/20 explicit | Count of active unsecured trades; feeds approval-strength penalty |
| F19 | city_tier | enum 1/2/3 (X+Y→1-2, Z→3) | A+D | ABCL/L&T/Union/Axis city-tier income + Axis 65-city service list | 9/20 | City → tier via GoI HRA X/Y/Z + lender lists; Axis non-listed city → CITY_NOT_SERVICED; pincode used only for lookup, never as a feature |
| F20 | residence_type | enum owned/rented/company/parental | A+D | IndusInd 1yr rented-stay; Yes 1yr permanent-address rules | 4/20 | Standardised enum; rented <12m → flag |
| F21 | salary_account_with_lender | lender-id or none | A | SBI mandatory; BoB/Canara/PNB/Union/Kotak/IDFC rate+limit benefits | 10/20 | Match applicant's salary bank to lender; drives rate concession + relaxed minima |
| F22 | requested_tenure_months | months (optional) | A | Tenure offer + maturity-age cap + APR ranking | 20/20 | Optional; default = min(lender max, maturity-capped max); allowed set {12,24,36,48,60,72,84,108} clipped per lender |
| F23 | age_at_application | years, 1dp | S←DOB+date | All age gates (SBI 21–60, Union 18+, HDFC 21–60, ICICI 18–58…) | 20/20 | (application_date − DOB)/365.25; never a stored age (IBL lesson — stored bureau Age is pull-date age) |
| F24 | age_at_maturity | years, 1dp | S | Maturity caps (Axis 60, SBI retirement/60, BoB 60/65, ICICI-SE 65, Bajaj 80, Tata-blog 65…) | 18/20 | F23 + tenure/12; evaluated at requested then at capped tenure |
| F25 | max_tenure_by_age_L | months, per lender | S | Tenure offer for older applicants (P06 age-57 case) | 18/20 | min(product_max_L, floor((maturity_cap_L − F23)×12)); <12 → AGE_AT_MATURITY reject |
| F26 | assessed_income_L | ₹/month, per lender | D+T | Each lender reads income differently (take-home vs gross; SE: latest vs 2yr-avg ITR/12) | 20/20 | Salaried: F07 (or GMI variant where BoB/PNB/Canara use gross — documented conversion). SE: lender's stated method, default latest-ITR/12 |
| F27 | total_obligations_L | ₹/month, per lender | B+T | FOIR numerator | 20/20 | F11 + F12×k_L − ending-soon EMIs; k=5% default (estimated); lender overrides stored |
| F28 | current_foir | ratio 0–2 | T | Pre-loan burden; headroom check | 20/20 | F27/F26; >1 flagged (already over-committed) |
| F29 | emi_capacity_L | ₹/month, per lender | T | Core affordability number → max loan | 20/20 | F26×foir_limit_L − F27; ≤0 → FOIR_EXCEEDED; capped at 2×income and flagged |
| F30 | post_loan_foir | ratio | T | Requested-amount affordability | 20/20 | (F27 + EMI(requested, r, n))/F26; reported on every offer |
| F31 | score_band | enum ≥800/750–799/700–749/650–699/<650/NTC | B+T | All published rate grids (Union 6-band, PNB 4-band, BoB employer×score…) | 20/20 | Band F13; NTC kept separate (priced with 750–799 at PNB/Union, rejected at HDFC/IndusInd/IDFC) |
| F32 | bureau_clean_flag | bool | B+T | Single clean/not-clean summary for explanations | 20/20 | TRUE iff F15<30 (or NULL-history) AND F17=FALSE; FALSE triggers estimated bureau reject |
| F33 | itr_income_growth | ratio or NULL | D+T | SE stability (declining income → reduced multiple) | 4/20 | (F08−F09)/F09; NULL if <2 ITRs; <−20% → flag + scorecard penalty |
| F34 | foir_headroom | ratio | T | Approval-strength + fix computation ("how close to the edge") | 20/20 | foir_limit_L − F28 (for requested loan: limit − F30); negative = over limit; drives counterfactual search |

Requested_amount is intentionally NOT a feature — it is the object being priced (excluded from the 30–35 count with this note). max_loan_by_foir / max_loan_by_multiple are outputs, not features. DOB/application_date exist only to compute F23.

---

## 7. Data preprocessing — exact instructions

Implement as pure, unit-tested functions (`src/eligibility/preprocess.py` in the build phase):

1. **Validate.** Reject (validation error, not lender REJECT) if: age <18 or >80; income ≤0 or >₹1 cr/month (flag >₹50L for review); tenure not in {3,6,9,12,18,24,36,48,60,72,84,108}; score not in 300–900/NULL; city unresolvable. Collect ALL errors, return together.
2. **Standardise units.** Income→₹/month; vintage/tenure→months; rates→% p.a. reducing-balance (convert flat rates if a source quotes flat: `r_reducing ≈ r_flat × 1.8` as interim, flagged estimated).
3. **Lender-specific conversions.** BoB/PNB/Canara gross-income products: `gross ≈ net/0.75` default (estimated, stored per lender, sensitivity-tested); ABCL take-home: use F07 directly.
4. **NULL discipline (IBL rule).** `bureau_score=NULL` (NTC), `max_dpd=NULL` (no history), `business_vintage=NULL` for salaried, `credit_history=NULL` — none imputed to 0. Only `existing_emi`/`card_outstanding` NULL→0 (no loans genuinely means zero obligation). XGBoost-style native-missing logic is mirrored here by explicit NTC branches per lender.
5. **Outlier clipping with flags.** Income <₹8k → flag (below any minimum); existing EMI > income → flag (FOIR>100%); enquiries >20 → cap at 20 + flag; DPD >180 → cap + flag. Flags flow to the explanation layer.
6. **City normalisation.** Lowercase/strip; alias table (Bengaluru↔Bangalore, etc.); map to tier via HRA X/Y/Z + Axis 65-city list + ABCL/L&T/Union tier rules; unmapped → `CITY_TIER_UNKNOWN` (validation error asking for nearest large city).
7. **Point-in-time correctness.** All ages computed at `application_date` (default today, overridable for backtesting). Bureau fields must carry `bureau_pull_date ≤ application_date` in the build-phase schema.
8. **Preprocessing tests:** ≥40 cases covering every boundary (score 649/650, income 24,999/25,001, age 20/21/60/61, NTC paths, city aliases, gross/net conversion).

---

## 8. Model architecture

**Per lender L, per applicant (deterministic, no randomness):**

1. **Derive** F23–F34. **2. Hard gates in fixed order** (record ALL failures): SEGMENT → SALARY_ACCOUNT (SBI) → PROFESSION allow-list (PNB-SE, Union-Prof) → RELATIONSHIP (Union non-salaried 24m, BoB >₹2L) → AGE → INCOME(city-tier) → EXP/VINTAGE/ITR → SCORE/NTC → BUREAU_HYGIENE (tiered, see below) → CITY_SERVED (Axis 65-city list) → MATURITY. **Tiered bureau hygiene (agreed policy; estimated, unlisted rules):** *banks* REJECT on DPD≥30 in 12m, ≥6 enquiries in 6m, or a write-off/settlement in 24m. *NBFCs* (Bajaj, Tata, ABCL, L&T, Poonawalla) REJECT on a write-off/settlement or DPD≥60, and for DPD 30–59 or ≥6 enquiries apply +3pp to the rate and a 50% amount haircut. *Fintechs* (Navi, KreditBee, Moneyview) REJECT on a write-off/settlement only where they publish a minimum score (Navi/Moneyview 650; KreditBee publishes that it accepts low scores), and otherwise apply +5pp and a 60% haircut. All thresholds are flagged estimated and go into the sensitivity analysis. **Conflict policy (agreed):** where a lender's own pages disagree, the engine uses the stricter value and keeps the alternative in `data/conflicts.csv` as a sensitivity case. **3. Size:** for each allowed tenure n: `loan_foir(n) = PV(emi_capacity_L, r_band, n)` via reducing-balance annuity; `loan_mult = assessed_income × multiple_L`; `max_loan_L(n) = min(loan_foir, loan_mult, product_max_L)`; offer only if ≥ product_min_L; amounts floored to ₹1,000. **4. Price:** rate from score-band grid (published where exists: Union/PNB/BoB/Canara; else `rate_min + band loading`, conservative upper-half for sizing, reported as range). APR via IRR on net disbursal (fee + 18% GST). **5. Status:** APPROVE (covers requested) / APPROVE_REDUCED / REJECT (reasons). **6. Overall:** eligible iff ≥1 APPROVE/REDUCED; else NOT ELIGIBLE + top blocking reasons + fixes. **7. Best option:** lowest APR among offers covering requested amount (else largest max loan); tie-breaks: approval-strength, then rule confidence; generated "why" text with rupee savings vs runner-up. **8. Approval-strength 0–100 (scorecard, weights published, never overrides gates):** score margin (30) + FOIR headroom (25) + stability/exp (15) + bureau hygiene (15) + relationship/employer (10) + amount-vs-multiple slack (5). Bands: ≥75 strong, 50–74 comfortable, 30–49 borderline, <30 weak-but-passing. **9. Counterfactual fixes** by monotone binary search (guaranteed by property tests): EMI to close, tenure extension, amount reduction, wait-months for exp/maturity, alternate lender. Non-actionable levers (age, history) are explained, never suggested.

---

## 9. Training process — calibration, NOT ML (instructions)

There is no `fit()` on applicant labels. "Training" = these five reproducible steps (build phase, `src/eligibility/calibrate.py`):

1. **Collect probe data.** For each lender with a calculator, run the §5 grid (≥60 probe points across income×EMI×age×tenure). Save raw input→max-loan pairs to `data/calibration/probes_{lender}_{date}.csv`. At least 20% of points per lender are held out (`*_holdout.csv`) and never used for fitting.
2. **Fit FOIR/multiples.** Least-squares fit of `max_loan = min(PV(income×foir − emi, r, n), income×mult, cap)` per lender; detect income-band kinks by piecewise fit (breakpoint only if ΔRMSE >10%). Output `foir_limit_L (+bands), multiple_L` with standard errors into the long rule table as `derived`.
3. **Fit maturity caps.** Tenure-cliff regression on age sweeps → `max_age_at_maturity_L`.
4. **Set scorecard weights.** Fixed at §8.8 values from underwriting judgement (not optimised). Any change requires a dated ADR entry + full golden-output re-run.
5. **Validate.** Report per-lender MAPE on held-out probes (target ≤10% on max loan for banks, ≤20% fintechs); publish the table in the README. If a lender fails, widen its reported ranges and downgrade its confidence — do not force-fit.
6. **Why no ML (for the README/interview):** no approval labels exist; bureau/outcome data is private; synthetic labels would be our own assumptions fed back to us (perfect circularity, zero evidence). Calibration error on held-out calculator outputs is the honest accuracy number.

---

## 10. Synthetic population for insights (never for training)

Sequential conditional sampler + Gaussian copula (public margins, assumed correlations), seed-fixed, n=100,000: employment (PLFS shares reweighted to credit-active via CIBIL/CRIF borrower mix) → age|employment (PLFS) → city tier (urban shares) → income-lognormal (PLFS earnings, age×city adjusted) → experience/tenure → hidden creditworthiness z (Beta, income-anticorrelated) → score bands (TransUnion published mix) + NTC share + DPD/enquiries/writeoff (z-driven) → EMIs (Beta share of income) + cards → requested amount multiple (lognormal) + tenure menu. Publish target-vs-generated table for every margin; run low/high-correlation variants; **an insight ships only if it holds in all variants**, labelled "under stated assumptions". Produces: binding-rule failure rates, approval heatmaps (income×score, employment×city), lender-count access histograms, shopping-around spreads, sensitivity of estimated rules ±20%.

---

## 11. Testing

1. **Unit tests** (`pytest`): every gate at threshold−1/at/+1 (age 20/21, score 649/650/719/720, income 24,999/25,001, exp 11/12m, DPD 29/30, enquiries 5/6, maturity edge). Every derived feature with hand-worked values. EMI/APR against closed-form checks.
2. **Property tests** (`hypothesis`, random profiles): more income ⇏ lower max loan; higher score ⇏ higher rate; more EMI ⇏ higher max loan; longer tenure ⇏ lower max loan (within maturity); NTC never out-scores 800 at the same lender. Violations = rule-table bugs.
3. **Golden-output tests:** §12 profiles' saved JSON must match byte-for-byte unless the rule table changed (then diff is reviewed and re-baselined with a dated note).
4. **Data-quality checks:** every long-table row has source+date; estimated rows have a method; no impossible values (min>max, foir>1, negative fees); conflict log entries all resolved.
5. **Calculator-accuracy check:** §9.5 holdout MAPE table — the report's honest accuracy number.

---

## 12. Sample profiles P01–P16 with computed outputs

These outputs are produced by the built engine (`src/eligibility/`), computed at
`application_date = 2026-01-01`, and are frozen as the golden test baseline
(`tests/golden/`, checked by `tests/test_phase7_golden.py`). The inputs live in
`tests/profiles/P01.json … P16.json`; reproduce any row with
`python -m eligibility evaluate tests/profiles/P01.json`.

**Method:** per lender/product — hard gates (incl. the tiered bureau policy) → size as
min(FOIR capacity, take-home-floor capacity, income multiple, product cap) with ICICI and
Kotak using their calibrated calculator formula → price by score band within the published
range (women's concession and NBFC/fintech repricing applied) → APR by IRR on
(loan − processing fee − 18% GST). "Top" offers are sorted by APR; "Best" is the lowest-APR
offer covering the requested amount. Strength is the 0–100 scorecard (§8.8 weights).


### P01 — Prime salaried, MNC, metro (32y, ₹1.2L/mo, score 800, EMI ₹15k) — wants ₹8L/48m
**Eligible: 18/20.** Top: Union APPROVE max ₹22.8L 9.25% APR 9.25% | IDFC APPROVE ₹10.0L 9.99% APR 9.99% | Canara APPROVE ₹41.6L 9.70% APR 10.01% | BoB APPROVE ₹20.0L 10.15% | Axis APPROVE ₹13.3L APR 10.16%. **Best: Union (APR 9.25%), strength 79/100.** SBI and Kotak reject (no SBI/Kotak salary account). The request is covered many times over, so the choice is pure price.

### P02 — Low score 640, DPD 30, 4 enquiries (35y, ₹80k, EMI ₹10k) — wants ₹5L/48m
**Eligible: 1/20.** Only KreditBee offers (APPROVE_REDUCED ₹3.84L, APR 35.9%), repriced for the bureau signals. **Best: KreditBee, strength 38/100.** Every bank rejects on `RECENT_DPD_GTE30`; most NBFCs reprice but the 640 score still blocks them. This is a bureau-driven outcome, not an income one.

### P03 — High existing EMI ~55% (38y, ₹1L, score 760, EMI ₹55k) — wants ₹6L/60m
**Eligible: 13/20** (several REDUCED). Top: Union REDUCED ₹2.35L 9.96% | Canara APPROVE ₹20.8L 10.96% (its take-home-floor rule gives the most room) | BoB APPROVE ₹20.0L 11.72% | ICICI APPROVE ₹6.9L 12.34% | IDFC REDUCED ₹2.2L. **Best covering the request: Canara, strength 64/100.** FOIR binds here, as expected for an EMI-heavy applicant.

### P04 — New job 4 months (27y, ₹90k, score 770, 36m total / 4m current) — wants ₹5L/36m
**Eligible: 10/20.** Top: IDFC APPROVE ₹10.0L 12.79% | ICICI APPROVE ₹29.3L 12.95% | Axis APPROVE ₹10.9L 13.18% | Yes APPROVE ₹16.1L 14.99% | Navi APPROVE ₹10.8L 15.17%. **Best: IDFC, strength 72/100.** HDFC/IndusInd/SBI/Tata/L&T reject on the 12-month current-job rule; the fix is to wait a few months.

### P05 — Fresher 21, 8 months exp, NTC (₹45k) — wants ₹2L/36m
**Eligible: 0/20 — NOT ELIGIBLE.** Top blocking: AGE_BELOW_MIN (18), NTC_NOT_ALLOWED (17), EXP_TOTAL_LT_MIN (11), EXP_CURRENT_LT_MIN (6). A no-score fresher just under the common 21/23 age bars has no public option; the advice is to build a few months of history and clear 21.

### P06 — Age 57, wants 60 months (₹1.5L, score 780, EMI ₹20k) — wants ₹10L/60m
**Eligible: 17/20.** Top: Union APPROVE ₹21.7L 9.96% | Canara APPROVE ₹39.9L 11.11% | BoB APPROVE ₹20.0L 11.72% | IDFC APPROVE ₹10.0L 12.79% | ICICI APPROVE ₹39.5L 12.95%. **Best: Union, strength 75/100.** Maturity caps shorten the usable tenure at lenders with a 60-year ceiling; the engine computes the per-lender tenure.

### P07 — Self-employed doctor (40y, ₹2L/mo, vintage 72m, score 790, 3 ITRs) — wants ₹15L/60m
**Eligible: 11/20** (salaried-only lenders reject). Top: Union APPROVE ₹40.0L 10.06% | ICICI APPROVE ₹40.0L 12.34% | IDFC APPROVE ₹40.0L 12.79% | BoB APPROVE ₹20.0L 13.20% | Tata APPROVE ₹36.0L 13.20%. **Best: Union, strength 82/100.** PNB's self-employed scheme excludes doctors, so PNB rejects — matching the published allow-list.

### P08 — Business owner, 2yr vintage, 1 ITR (36y, ₹1.2L, score 720) — wants ₹10L/48m
**Eligible: 9/20.** Top: Union APPROVE ₹24.0L 11.42% | BoB APPROVE ₹20.0L 14.70% | Tata APPROVE ₹21.6L 14.70% | IDFC APPROVE ₹24.0L 16.29% | IndusInd APPROVE ₹24.0L 18.94%. **Best: Union, strength 71/100.** Lenders needing 2 ITRs/financials (ICICI, L&T) reject on the single filing; PNB has no business-owner product.

### P09 — New-to-credit, no score (29y, ₹70k, no EMIs) — wants ₹4L/36m
**Eligible: 1/20.** Poonawalla-Prime (which publishes an NTC-allowed policy) APPROVE ₹8.4L, APR 25.29%. **Best: Poonawalla, strength 71/100.** Everyone else needs a score (`NTC_NOT_ALLOWED`). Confirms the NULL-score ≠ 0 handling: NTC is treated as "no history", not a bad score.

### P10 — DPD 60 in 12m, score 720 (34y, ₹95k) — wants ₹6L/48m
**Eligible: 3/20.** Navi REDUCED ₹4.56L 25.09% | KreditBee REDUCED ₹4.0L 27.01% | Moneyview REDUCED ₹4.0L 30.37%. **Best: Navi, strength 54/100.** Published gates pass on the 720 score, but bureau hygiene decides the case: banks reject, fintechs reprice. This is the "unlisted rule" the brief asks about.

### P11 — 9 enquiries in 6 months (31y, ₹1.1L, score 710) — wants ₹7L/48m
**Eligible: 7/20.** Top: L&T APPROVE ₹9.6L 22.35% | Navi REDUCED ₹5.3L 24.93% | Bajaj APPROVE ₹9.2L 25.17% | KreditBee REDUCED ₹4.0L 27.01% | Tata APPROVE ₹8.9L 27.53%. **Best: L&T, strength 61/100.** Banks reject on `EXCESS_ENQUIRIES`; NBFCs reprice. A short cooling-off period reopens the banks.

### P12 — Tier-3 city, ₹22k income (30y, score 730) — wants ₹1.5L/36m
**Eligible: 6/20.** Top: Canara APPROVE ₹6.6L 12.50% | BoB APPROVE ₹5.9L 13.68% | IDFC APPROVE ₹3.7L 16.29% | KreditBee APPROVE ₹2.6L 23.17% | Poonawalla APPROVE ₹2.6L 25.29%. **Best: Canara, strength 74/100.** Lenders with a ₹25–30k flat floor reject on income; the lower-floor PSU banks and fintechs remain.

### P13 — High earner wants ₹50L (42y, ₹3L/mo, score 810) — wants ₹50L/60m
**Eligible: 18/20.** Top: Union APPROVE ₹60.0L 9.25% | Canara APPROVE ₹142.2L 9.75% | Axis APPROVE ₹50.0L 9.93% | IDFC APPROVE ₹60.0L 9.99% | HDFC REDUCED ₹40.0L 10.07%. **Best: Union, strength 83/100.** Product caps, not multiples, bind at high income — HDFC's ₹40L cap means it cannot cover the ₹50L request.

### P14 — Govt employee, SBI salary account (45y, ₹85k, score 760) — wants ₹12L/60m
**Eligible: 17/20.** Top: Union APPROVE ₹17.0L 9.83% | Canara APPROVE ₹39.4L 10.91% | SBI APPROVE ₹25.4L 11.65% | BoB APPROVE ₹20.0L 11.72% | ICICI APPROVE ₹27.6L 12.34%. **Best: Union, strength 76/100.** SBI now passes — this is the one profile with the SBI salary account its product requires.

### P15 — Exactly at thresholds (21y, ₹25k, score 700, exp 12/12m) — wants ₹3L/36m
**Eligible: 1/20.** IDFC APPROVE ₹4.24L, APR 16.29%. **Best: IDFC, strength 55/100.** A boundary profile: 700 clears ≥700 gates but fails lenders whose stricter resolved minimum is higher, and the ₹25k income sits exactly on several floors. It just barely qualifies somewhere.

### P16 — Settled loan 18m ago (39y, ₹90k, score 680) — wants ₹5L/48m
**Eligible: 1/20.** Only KreditBee offers (REDUCED ₹4.0L, APR 30.98%), the lone lender lenient on a settlement. **Best: KreditBee, strength 48/100.** Banks and the score-publishing fintechs reject on `PRIOR_WRITEOFF_SETTLEMENT`; the 680 score blocks several more. Clean months plus a higher score reopen the market.

---

## 13. Insights (full population simulation in build phase)

1. **Unpublished bureau rules decide more cases than income.** In 4/16 profiles the outcome is set by unlisted bureau rules (DPD, enquiries, settlement) while all published gates pass. These are exactly the "rules that are not listed" the brief asks about. With the tiered policy, banks reject these profiles, while NBFCs and fintechs reprice them or cut the amount.
2. **New-to-credit applicants have far fewer options.** Only PNB, Union and KreditBee publish that they accept or price new-to-credit applicants. SBI accepts them only with an SBI salary account. Most other lenders don't publish a policy, and under the stricter-value rule the engine treats that as no.
3. **Self-employment cuts the market sharply.** 6/20 lenders are salaried-only. PNB's self-employed track takes only listed professions, and Union's needs an existing relationship or a ₹12L income. Vintage and ITR gates remove more. The exact count comes from the engine.
4. **FOIR binds before multiples** for EMI-heavy applicants (P03); **product caps bind before both** for high earners (P13).
5. **Tenure is the silent gate for older applicants** (P06) via maturity caps, not application-age caps.
6. **Shopping around is worth several percentage points of APR on the same profile** (v0.1 spread for P01 is roughly 10.4% to 14%+). The exact spread will be recomputed with real fees and rate grids. Fintechs are competitive only where their fee is low, and their maximum loans are smaller.
7. **Sensitivity (build phase):** bureau-hygiene thresholds and FOIR ±20% move approvals most; fee% moves APR ranking but rarely eligibility. Calculator-accuracy holdouts will quantify.

**Limitations (state in README):** internal scorecards/employer allow-lists/document checks are invisible; fintech pricing is personalised (wide ranges, low confidence); rules change (every value dated); bureau-hygiene thresholds are estimated unlisted rules; simulation insights hold only under stated assumptions. **Next:** Playwright calculator probes → derived FOIR/multiples → holdout MAPE → population sim → Streamlit + CLI.

---

## 14. Run instructions and repo contract

Repo root = `C:\Users\rudra\Desktop\Resume\Birbal\Model`. Contract (build phase): `data/variables.csv` (34 features + units/types/origins), `data/lender_rules_long.csv` + generated `lender_rules_wide.csv`, `data/sources/*` snapshots, `src/eligibility/` (schema, preprocess, rules, affordability, pricing, engine, counterfactual, calibrate, simulate, cli), `app/streamlit_app.py`, `tests/` (profiles P01–P16 + outputs + test_*.py), `README.md` (brief-mandated content). Setup: Python 3.11 venv, `pip install -r requirements.txt` (pandas numpy scipy pydantic pytest hypothesis streamlit playwright; `playwright install chromium`), `python -m eligibility evaluate tests/profiles/P01.json`, `pytest`, `streamlit run app/streamlit_app.py`. **Do not commit IBL files, real bureau XML, or any customer data.**

---

## Appendix A — reason-code dictionary

| Code | Meaning | Fix hint |
|---|---|---|
| SEGMENT_NOT_OFFERED | Lender has no product for SEP/SEB | Try SE-tolerant lender (BoB/PNB/Union/ICICI/Bajaj/Tata/ABCL/L&T/Navi/KreditBee/Moneyview) |
| AGE_BELOW_MIN / AGE_ABOVE_MAX | Outside application-age window | Wait / choose higher-max lender (Bajaj 80-maturity, Union-SE 75) |
| AGE_AT_MATURITY | Tenure breaches maturity cap | Shorten tenure (computed max offered) |
| INCOME_BELOW_MIN | Below city-tier minimum | ABCL-T2/Union/KreditBee have lowest floors; document higher take-home |
| EXP_TOTAL_LT_MIN / EXP_CURRENT_LT_MIN | Experience gate | Wait N months (computed); or Poonawalla-Prime (6m/1m) / KreditBee (2–3m) |
| VINTAGE_LT_MIN | Business vintage < required | Wait; or KreditBee (no vintage stated) |
| SCORE_BELOW_MIN | Below published/preferred floor | Build score; drop to lower-floor lender |
| NTC_NOT_ALLOWED | Lender needs a score | SBI/PNB/Union/KreditBee only |
| RECENT_DPD_GTE30 (est.) | ≥30 DPD in 12m | 6–12 clean months |
| EXCESS_ENQUIRIES (est.) | ≥6 enquiries/6m | 3–6m cooling, no fresh applications |
| PRIOR_WRITEOFF_SETTLEMENT (est.) | Write-off/settlement 24m | 12–24 clean months; KreditBee first |
| FOIR_EXCEEDED | No EMI headroom | Close ₹X EMI (computed) / longer tenure / lower amount |
| AMOUNT_BELOW_MIN | Eligible < product minimum | Take minimum ticket or another lender |
| CITY_NOT_SERVICED | Axis non-listed city etc. | Another lender |

## Appendix B — v0.1 rule table (access 2026-10-09/10; P=published, A=aggregator, E=estimated)

| Lender | Age | Income/mo | Exp | Score / NTC | FOIR/mult | Amount | Tenure | Rate% | Fee%+GST | SE | Key source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SBI | 21–60, mat. retirement/60 | ₹20k govt/def, ₹25k corp (P) | 6m govt, 12m corp (P) | 650 def/govt, 670 corp; NTC ok (P) | 65% + 30× (P) | ₹1L–₹50L (P) | 6–84 (P) | 10.00–15.00, mean 11.54 (P) | ≤1.5 (₹1k–15k); waivers (P) | No | sbi.bank.in personal-loan + FAQ + ROI pages |
| HDFC | 21–60 | ₹25k (P) | 24m tot + 12m curr (P) | 720 min (P); NTC NF→No (E) | 0.60/20× (E) | ₹25k–₹50L (75L cond.) (P, confl.) | 12–60 (72 festive) (P) | 9.99–24.00; avg IRR 10.89 (P) | ≤₹6,500 flat (P) | No (P) | hdfc.bank.in eligibility + rates pages |
| ICICI | 18/20–58 (confl. P) | ₹30k (P) | 24m tot (P) | 700/750 pref (confl. P) | 0.60/20× (E) | ₹50k–₹50L (P) | 12–84 (P) | 9.99–16.50; mean 11.45 (P) | ≤2% (P) | Yes, 23y–65, 2y biz + 3y exp, 2y financials (P) | icici.bank.in eligibility + rates + charges |
| Axis | mat. ≤60 (P); app NF | ₹15k Axis-cust / ₹25k other (confl. P); tier-based | ~12m doc (P-partial) | 750 healthy-guidance (P); NTC NF→No (E) | 0.60/20× (E) | ₹50k–₹50L (P) | 12–84 (P) | 9.99–22 (8.90–21.55 MCLR table confl.) (P) | ≤2% (P) | No | axis.bank.in loans/personal-loan + eligibility-documentations + 65-city tier list |
| Kotak | 21–60 (80* typo confl.) | ₹30k (₹25k Kotak-sal) (P) | 12m tot (P) | 685 FAQ / 750 table (confl. P) | 0.60/20× (E) | ₹50k–₹1cr (P) | 12–72 (P) | from 10.99, max NF (P-part) | ≤5% (P) | No (unconfirmed) | kotak.com eligibility + rates + fees pages |
| BoB | 21+, mat. 60 (65 SE) (P) | NF (E: no floor) | 12m continuous (P) | NF, score-linked pricing (P) | 40–75% GMI by tier (P) / 20× (E) | ₹0.5–1L min – ₹20L (P) | ≤84/72/48–60 by tier (P) | 10.15–18.00 by tier (P) | 1–2% (₹1k–10k); govt-BoB-sal nil (P) | Yes, 1y stable (2y agents), 1y ITR (P) | bankofbaroda.in baroda-personal-loan |
| PNB | NF (21–60 NTB digital) | NF (E) | 24m PNB-sal / 36m check-off (P) | no floor, <681 band; NTC=750-band (P); SE-prof 750 (P) | 24× salaried / 10× SE-prof ≤₹5L (P); FOIR number NF | ≤₹20L sal / ≤₹5L SE (P) | ≤72 (60 defence; 60 SE) (P) | 10.50–16.05 by employer×score (P) | 1% (def nil) + doc (P) | Prof-only allow-list + ₹6L×2y + 2y PNB relation (P); no SEB | pnb.bank.in personalloanforpublic + ROI + charges + FAQ |
| Canara | NF (E) | NF (E) | 12m confirmed (P) | CRG 1–4 grid, mapping NF; Delight-CRG4 INELIGIBLE (P) | take-home ≥25% or ₹10k after EMIs (P); 25× gross ≤₹50L/40L (P) | ≤₹50L Prime / ₹40L Delight (P) | ≤84 (P) | 9.70–14.70, mean 11.86 (P) | 0.5% (₹1k–5k) (P) | No | canarabank.bank.in canara-budget + RLLR + fixed-rate + range pages |
| Union | 18+, mat. retire−1y (60 SE-prof exit 65, non-sal 75) (P) | ₹15k (₹20k 7 metros) (P) | none stated (P) | no floor, <650 band; NTC=750-band (P) | 0.60/15× (E) | ₹5–15L by history (P); Prof ≤₹20L | ≤60 (84 govt/W-prof) (P) | 9.30–12.90 by score (EBLR 8.25, P) | 1% (₹1k–10k from 20.10.26); Prof nil (P) | Yes: non-sal regular income + 24m relation; Prof CA/CS/Dr/Engg ₹12L + 3y ITR (P) | unionbankofindia.bank.in scheme pages + retail_roi.pdf + service-charges PDFs |
| IndusInd | 21+, mat. 60/retire (P) | ₹25k online (P) | 24m + 12m curr (P) | 730 min (P) | 0.60/20× (E) | ₹30k–₹50L (₹5L instant) (P) | 12–84 (48 online) (P) | from 10.49, max NF (P-part) | ≤3.5% (P) | Yes: 25–65, ₹4.8L net, 4–5y post-qual (P) | indusind.bank.in personal-loan + rate + SOC PDF |
| IDFC | FIRSTmoney 21–60; HL 23–60-mat (P) | ₹10k FIRSTmoney (P); HL NF | NF (E) | 710 sal / 760 SE FIRSTmoney (P); HL 730-ideal | 0.60/20× (E) | ₹50k–₹15L FM / ₹1L–₹1cr HL (P) | 9–60 FM / 12–84 HL (P) | from 9.99 (P) | 0–3.5% (GST wording confl.) (P) | Yes FM (P); HL unclear | idfcfirst.bank.in personal-loan + higher-limit + rates + fees + eligibility-calculator |
| Yes | 21–60 (P) | ₹25k (P) | 12m (P) | 700 (P) | 0.60/20× (E) | ₹50k–₹50L (P) | 12–72 (P) | 10.85–21 (FAQs confl.) (P) | ≤2.5% (P) | Likely no (P-partial) | yes.bank.in personal-loan + eligibility + rates + KFS template |
| Bajaj | 21+, mat. 80 (P) | ₹25,001 city-varied (P) | stable-employment (P, unquantified) | 650 floor (P; 685/760 variants) | 50–60% generic-text (E); mult NF→18× (E) | ₹40k–₹55L (P) | 12–108 (P) | 10–30.5 fixed (P) | ≤4.13% incl. tax (P) | Yes (P; business-loan terms on SE page) | bajajfinserv.in personal-loan + salary + calculator + interest-rate-policy Mar-2026 PDF |
| Tata | 21–58 (mat. 65 blog) (P) | ₹20k (₹15k confl.) (P) | 24m + 12m curr (P, confl. 12m) | 725 preferred (P) | 40–50% + 9–18× guidance-text (E) | ₹40k–₹35L (75k confl.) (P) | 12–72 (P) | 10.99–33, APR ≤45 (P) | ≤5% (P) | Yes, ₹20k + 2y financials (P); vintage NF | tatacapital.com eligibility-calculator + rates-and-charges + product + docs pages |
| ABCL | 21/23–60 (62 ext.) (P) | ₹25k Mum/Del, ₹20k T1, ₹18k T2–4 (P) | 6m current (P) | 700 (650/750 confl.) (P) | NF→0.60/20× (E) | ~₹50k–₹65L (P) | 12–84 (P) | from 10.99; policy 10–28 cap 28 (P) | ≤4% phys / ≤6% digital (P) | Contradictory pages; SE page: 21–60, 700+, 2y ITR (P) | adityabirlacapital.com eligibility + product + rates + fee schedules + rate-policy V4 |
| L&T | 21–58 (P) | ₹25k T1 / ₹15k T2–3 (P) | 12m current (P) | 700 (P; <650 decline-or-price) | 50–55% generic (E); 10–18× generic (E) | ₹50k–₹30L (₹15L SE-FAQ) (P) | 12–72 (P) | 10.50–24 policy (P) | 4% (3% confl.) (P) | Yes: 25–65 (21–58 confl.), 2y vintage + 2y ITR (P) | ltfinance.com product + calculators + rate + fees + rate-model v8.0 PDF |
| Poonawalla | Reg 21–60 / Prime 23–58-mat / Inst 24–55 (P) | ₹25k reg / ₹22k Prime / ₹3L-hh Inst (P) | 12m/1m reg, 6m/1m Prime (P) | 700 ideal (P); Prof 750-guide | NF→0.60/20× (E) | ₹1L–50L reg / ≤15L Prime / ₹50k–5L Inst (P) | 12–84 (12–36 Inst) (P) | from 9.99 / 12.65 Prime / 16 Inst (P) | ≤4% reg / ≤5% Inst (P) | Inst + Professional Loan (24–65, 1y post-qual, ₹3L, 750-guide, ₹1–75L, 13%+) (P) | poonawallafincorp.com eligibility + rates + prime + instant + professional pages |
| Navi | 21–65 blog (P-blog); 18–65 A | ₹3L household (T&C) (P) | NF (E) | 750 snippet / 650 blog (P-part) | NF→0.60/15× (E) | ≤₹20L (P) | ≤84 (48/72 confl.) (P) | ≤29.96, from 9.9 snippet (P-part) | zero snippet vs 3.99–6% A (confl.) | Yes, no ITR per blogs (P-blog) | navi.com T&C + finserv + LSP pages; product pages JS-blocked (snippet) |
| KreditBee | 21–60 (P) | ₹10k personal + ₹25k household (P) | 2–3m current (confl. P) | none — low-score + NTC ok (P) | NF→0.60/12× (E) | ₹3–6k min (confl.) – ₹10L (P) | 3/6–60 (confl.) (P) | 12–27.5/28.5 (confl.), APR 17–50 (P) | ≤4.7% (Flexi ₹350–16.8k) (P) | Yes, no ITR, 6m stmts (P); vintage NF | kreditbee.in PL + salaried + SE + flexi + proprietorship + Play listing |
| Moneyview | 21–57 (P) | ₹25k household/in-hand (P) | NF (E) | 650 (P) | NF→0.60/12× (E) | ₹5k–₹10L (P) | 3–60 (72 calc) (P) | 1.16–3%/mo, from 14% p.a., APR 17–45 (P) | from 2% (≤8% city pages) (P) | Yes, same rules; 3m stmts; ITR 2–3y tip (P-part) | moneyview.in PL + FAQ + partners + SE + eligibility + Play listing |

 Benchmarks at access: Union EBLR 8.25% (repo 5.50% + 2.75%, w.e.f. 08.10.26; same PDF also shows 8.00% on 30.09.26 — logged conflict); PNB RLLR 8.35% (08.10.26); Canara RLLR 8.00% (12.03.26); SBI 2Y-MCLR 8.75%; ICICI 1Y-MCLR 8.40%; Axis 3Y-MCLR 8.90%.

## Appendix C — glossary + key sources

FOIR (fixed-obligations-to-income ratio); DPD (days past due); APR (annualised IRR incl. fees/GST — KFS method); KFS (RBI-mandated Key Facts Statement); EBLR/RLLR/MCLR (external/repo-linked/marginal-cost benchmarks); CRG (Canara risk grade); OOF (out-of-fold — IBL method reused for portfolio-rate features if added); NTC (new-to-credit). System sources: CRIF How India Lends Sep-2026 (https://www.crifhighmark.com/media/7548/how-india-lends-september-2026.pdf); FACE Q1FY27 via Business Today 01-10-2026; RBI risk-weight circulars Nov-2023 (summarised by Moneycontrol/CNBC-TV18); GoI HRA OM 2/5/2017-E.II(B) 07-07-2017 (X/Y/Z tiers for city mapping); Axis 65-city tier list (https://www.axis.bank.in/loans/personal-loan). Lender sources: exact URLs in Appendix D, all accessed 2026-10-09/10. The per-value URL for each rule goes into `data/lender_rules_long.csv`.

## Appendix D — exact source URLs (accessed 2026-10-09/10)

| Lender | URLs |
|---|---|
| SBI | https://sbi.bank.in/web/personal-banking/loans/personal-loans/sbi-personal-loan · https://sbi.co.in/web/faq-s/faq-personal-loan/ · https://sbi.bank.in/web/interest-rates/interest-rates/loan-schemes-interest-rates/personal-loans-schemes |
| HDFC Bank | https://www.hdfc.bank.in/personal-loan/eligibility · https://www.hdfc.bank.in/personal-loan · https://www.hdfc.bank.in/personal-loan/interest-rates-and-charges |
| ICICI Bank | https://www.icici.bank.in/personal-banking/loans/personal-loan/eligibility · https://www.icici.bank.in/personal-banking/loans/personal-loan · https://www.icici.bank.in/personal-banking/loans/personal-loan/personal-loan-interest-rates · https://www.icici.bank.in/personal-banking/loans/personal-loan/service-charges |
| Axis Bank | https://www.axis.bank.in/loans/personal-loan · https://www.axis.bank.in/loans/personal-loan/eligibility-documentations · https://www.axis.bank.in/loans/personal-loan/interest-rates-charges |
| Kotak | https://www.kotak.com/en/personal-banking/loans/personal-loan/eligibility.html · https://www.kotak.com/en/personal-banking/loans/personal-loan.html · https://www.kotak.com/en/personal-banking/loans/personal-loan/interest-rates.html · https://www.kotak.com/en/personal-banking/loans/personal-loan/fees-and-charges.html |
| Bank of Baroda | https://www.bankofbaroda.in/personal-banking/loans/personal-loan/baroda-personal-loan |
| PNB | https://pnb.bank.in/personalloanforpublic.html · https://pnb.bank.in/Retail-Advances-interst-rate-on-advances-linked-to-mclr.html · https://pnb.bank.in/interst-rate-on-advances-linked-to-mclr.html · https://pnb.bank.in/service-charges-related-to-retail-advances.html · https://pnb.bank.in/FAQ-PERSONAL-LOAN.html · https://pnb.bank.in/NTBPL.html |
| Canara Bank | https://www.canarabank.bank.in/canara-budget · https://www.canarabank.bank.in/rates-of-interest-for-retail-lending-schemes-linked-to-rllr · https://www.canarabank.bank.in/interest-for-retail-lending-schemes-linked-to-fixed-rate-of-interest · https://www.canarabank.bank.in/pages/interest-rate-range-on-loans |
| Union Bank | https://unionbankofindia.bank.in/en/Details/union-personal-salaried-individual-other-than-government-employee · https://unionbankofindia.bank.in/en/Details/union-personal-loan-non-salaried · https://unionbankofindia.bank.in/en/Details/union-professional-personal-loan-scheme · https://unionbankofindia.bank.in/en/Details/union-women-professional-personal-loan-scheme · https://unionbankofindia.bank.in/en/Details/personal-loan-under-special-retail-lending-scheme-for-government-employees · https://unionbankofindia.bank.in/pdf/retail_roi.pdf · https://unionbankofindia.bank.in/pdf/Service%20Charges-Domestic%20Rupee%20Advances-Corp%20Website.pdf |
| IndusInd | https://www.indusind.bank.in/in/en/personal/loans/personal-loan.html · https://www.indusind.bank.in/in/en/personal/loans/personal-loan/personal-loan-interest-rate.html · https://www.indusind.bank.in/content/dam/indusind-corporate/schedule-of-charges/others/Personal-Loan-SOC.pdf |
| IDFC FIRST | https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan · https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/higher-limit · https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/personal-loan-interest-rates · https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/fees-and-charges · https://www.idfcfirst.bank.in/personal-banking/loans/personal-loan/personal-loan-eligibility-calculator |
| Yes Bank | https://www.yes.bank.in/personal-banking/loans/personal-loan · https://www.yes.bank.in/personal-banking/loans/personal-loan/eligibility-criteria · https://www.yes.bank.in/personal-banking/loans/personal-loan/interest-rates · https://www.yes.bank.in/pdf?name=ybl_pl%20_kfs_english.pdf |
| Bajaj Finance | https://www.bajajfinserv.in/personal-loan · https://www.bajajfinserv.in/minimum-salary-required-for-personal-loan · https://www.bajajfinserv.in/personal-loan-eligibility-calculator · https://www.bajajfinserv.in/personal-loan-for-self-employed · https://cms-assets.bajajfinserv.in/is/content/bajajfinance/interest-rate-policy-march-2026-final?scl=1&fmt=pdf |
| Tata Capital | https://www.tatacapital.com/personal-loan/eligibility-calculator.html · https://www.tatacapital.com/personal-loan/rates-and-charges.html · https://www.tatacapital.com/personal-loan.html · https://www.tatacapital.com/personal-loan/documents-required.html |
| Aditya Birla Capital | https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/eligibility-criteria · https://www.adityabirlacapital.com/loans/personal-finance/personal-loan · https://www.adityabirlacapital.com/loans/personal-finance · https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/interest-rates · https://www.adityabirlacapital.com/loans/personal-finance/personal-loan/loan-for-self-employed · https://www.adityabirlacapital.com/-/media/ABCL/pdf/Aditya-Birla-Finance-Limited/ABCL-Interest-rate-policy-V4.ashx |
| L&T Finance | https://www.ltfinance.com/personal-loan · https://www.ltfinance.com/personal-loan-eligibility-calculator · https://www.ltfinance.com/personal-loan-for-salaried · https://www.ltfinance.com/personal-loan-for-self-employed · https://www.ltfinance.com/personal-loan-interest-rate · https://www.ltfinance.com/personal-loan-fees-and-charges |
| Poonawalla | https://poonawallafincorp.com/personal-loan/eligibility-and-documents · https://poonawallafincorp.com/personal-loan/interest-rates-and-charges · https://poonawallafincorp.com/personal-loan/prime-personal-loan-for-salaried-employees · https://poonawallafincorp.com/instant-personal-loan/eligibility-and-document · https://poonawallafincorp.com/professional-loan/eligibility-and-documents |
| Navi | https://navi.com/terms-and-conditions/cash-loan · https://navi.com/finserv · https://navi.com/finserv/lsp-dla · https://www.mymoneymantra.com/navi-personal-loan (aggregator, fee only) |
| KreditBee | https://www.kreditbee.in/personal-loan · https://www.kreditbee.in/personal-loan-for-salaried · https://www.kreditbee.in/personal-loan-for-self-employed · https://www.kreditbee.in/flexi-personal-loan · https://play.google.com/store/apps/details?id=com.kreditbee.android |
| Moneyview | https://moneyview.in/personal-loan · https://moneyview.in/loans-faq-en · https://moneyview.in/our-lending-partners · https://moneyview.in/loans/instant-personal-loan-for-self-employed · https://moneyview.in/personal-loan-eligibility-check · https://play.google.com/store/apps/details?id=com.whizdm.moneyview.loans |

*End of model_report.md — approved build order: lender list (§3) → rule table (App. B) → engine (§8) → calibration (§9) → tests (§11) → app + README.*
