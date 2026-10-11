# plan2 EDGE profiles — engine results

Generated 2026-10-11 by `scripts/run_edge_profiles.py` over the real engine (`eligibility.engine.Engine`). Inputs are the 10 EDGE profiles from `prompts/plan2_inputs.md` (stored in `tests/edge_profiles/`).

All figures are screening estimates against published lender criteria — not loan offers. APR is an IRR on net-of-fee cash flows; `*` marks an indicative APR (rate estimated).

## Summary

| Profile | Description | Age | Pass screening | Cover exact request | Best lender | Best APR |
|---|---|---|---|---|---|---|
| EDGE01 | Boundary case: credit score exactly 700 and FOIR near 50% | 30.4 | 15/20 | 2/20 | CANARA | 12.16% |
| EDGE02 | Low credit score, serious recent DPD, and multiple enquiries | 34.3 | 1/20 | 0/20 | KREDITBEE | 35.72% |
| EDGE03 | Existing EMI obligations already exceed a 50% FOIR threshold | 32.2 | 13/20 | 0/20 | CANARA | 10.9% |
| EDGE04 | Changed jobs recently: four months with current employer | 27.8 | 11/20 | 5/20 | IDFC | 12.79% |
| EDGE05 | Young applicant, eight months of experience, and no established credit history | 21.2 | 0/20 | 0/20 | - | - |
| EDGE06 | Age 57 with a requested tenure of 60 months | 57.7 | 17/20 | 0/20 | CANARA | 10.97% |
| EDGE07 | Established self-employed doctor with high income and strong credit | 41.1 | 13/20 | 2/20 | NAVI | 10.09% |
| EDGE08 | Self-employed business owner with two-year business vintage and one ITR | 37.7 | 9/20 | 0/20 | IDFC | 12.79% |
| EDGE09 | High-income applicant requesting a large personal loan of 50 lakh | 35.9 | 17/20 | 3/20 | CANARA | 9.73% |
| EDGE10 | Good credit score but a loan settlement occurred 18 months ago | 38.1 | 1/20 | 0/20 | KREDITBEE | 27.03% |

## EDGE01 — Boundary case: credit score exactly 700 and FOIR near 50%

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE01",
  "description": "Boundary case: credit score exactly 700 and FOIR near 50%",
  "date_of_birth": "1996-05-10",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 60000,
  "existing_monthly_emi": 15000,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 700,
  "total_experience_months": 72,
  "current_job_tenure_months": 36,
  "employer_category": "private_ltd",
  "city": "Pune",
  "salary_account_with": "none",
  "requested_amount": 450000,
  "requested_tenure_months": 36
}
```

- Completed-years age: **30** (exact 30.4); bureau state: **valid**
- Products passing screening: **15/20**; covering the exact Rs 450,000 / 36m request: **2/20**
- Best option: **CANARA — Canara Budget** (Eligible (requested terms)); APR 12.16%
  - Lowest APR (12.16%) among 2 eligible products covering the exact requested amount and tenure; nominal rate 11.95%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| CANARA | Canara Budget | Eligible (requested terms) | Rs 14,936 | Rs 2,000,000 | 9.7-14.7% | 12.16% | 63 | multiple |
| ICICI | Icici Personal Loan | Eligible (requested terms) | Rs 15,145 | Rs 1,250,000 | 9.99-16.5% | 14.6% | 58 | calculator |
| BOB | Baroda Personal Loan | Preliminarily eligible | Rs 15,310 | Rs 1,600,000 | 10.15-18.0% | 13.68% | 61 | multiple |
| UNION | Union Women Professional | Preliminarily eligible | Rs 15,533 | Rs 1,200,000 | 12.0-18.0% | 14.7%* | 58 | multiple |
| IDFC | Idfc Higher Limit | Preliminarily eligible | Rs 15,885 | Rs 1,048,000 | 9.99-24.0% | 16.29% | 58 | foir |
| AXIS | Axis Personal Loan | Preliminarily eligible | Rs 15,553 | Rs 469,000 | 8.9-22.0% | 16.49% | 50 | foir |
| YES | Yes Personal Loan | Preliminarily eligible | Rs 15,692 | Rs 982,000 | 10.85-21.0% | 17.56% | 58 | foir |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 15,948 | Rs 852,000 | 10.49-24.0% | 19.61% | 57 | foir |
| LNT | Lnt Personal Loan | Preliminarily eligible | Rs 15,948 | Rs 681,000 | 10.5-24.0% | 20.06% | 55 | foir |
| NAVI | Navi Cash Loan | Preliminarily eligible | Rs 16,479 | Rs 720,000 | 9.9-29.96% | 20.38% | 57 | multiple |
| KREDITBEE | Kreditbee Flexi Personal Loan | Preliminarily eligible | Rs 16,491 | Rs 720,000 | 12.0-27.5% | 22.28% | 57 | multiple |
| BAJAJ | Bajaj Personal Loan | Preliminarily eligible | Rs 16,548 | Rs 767,000 | 10.0-30.5% | 22.9% | 55 | foir |
| POONAWALLA | Poonawalla Prime Pl | Preliminarily eligible | Rs 17,114 | Rs 720,000 | 9.99-36.0% | 25.29% | 57 | multiple |
| TATA | Tata Personal Loan | Preliminarily eligible | Rs 16,928 | Rs 612,000 | 10.99-33.0% | 25.41% | 54 | foir |
| MONEYVIEW | Moneyview Personal Loan | Preliminarily eligible | Rs 17,631 | Rs 720,000 | 14.0-36.0% | 25.69% | 57 | multiple |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **BOB** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **UNION** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **IDFC** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **AXIS** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **YES** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **INDUSIND** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **LNT** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **NAVI** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **KREDITBEE** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **BAJAJ** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **POONAWALLA** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **TATA** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **MONEYVIEW** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`
- **HDFC** (Not eligible): `SCORE_BELOW_MIN`
- **KOTAK** (Not eligible): `SCORE_BELOW_MIN`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`
- **ABCL** (Not eligible): `SCORE_BELOW_MIN`

</details>

## EDGE02 — Low credit score, serious recent DPD, and multiple enquiries

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE02",
  "description": "Low credit score, serious recent DPD, and multiple enquiries",
  "date_of_birth": "1992-06-10",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 120000,
  "existing_monthly_emi": 10000,
  "card_outstanding": 300000,
  "has_credit_score": true,
  "bureau_score": 640,
  "max_dpd_days_last_12_months": 60,
  "enquiries_last_6_months": 9,
  "total_experience_months": 96,
  "current_job_tenure_months": 48,
  "employer_category": "mnc",
  "city": "Mumbai",
  "salary_account_with": "hdfc",
  "requested_amount": 500000,
  "requested_tenure_months": 36
}
```

- Completed-years age: **34** (exact 34.3); bureau state: **valid**
- Products passing screening: **1/20**; covering the exact Rs 500,000 / 36m request: **0/20**
- Best option: **KREDITBEE — Kreditbee Flexi Personal Loan** (Preliminarily eligible); APR 35.72%
  - Lowest APR (35.72%) among 1 eligible products offering the closest affordable alternative (the request is not fully covered); nominal rate 32.5%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| KREDITBEE | Kreditbee Flexi Personal Loan | Preliminarily eligible | Rs 21,916 | Rs 400,000 | 12.0-27.5% | 35.72% | 34 | product |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| ICICI | Icici Personal Loan | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| BOB | Baroda Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| UNION | Union Personal All | Not eligible | - | - | - | - | - | - |
| INDUSIND | Indusind Personal Loan | Not eligible | - | - | - | - | - | - |
| IDFC | Idfc Firstmoney | Not eligible | - | - | - | - | - | - |
| YES | Yes Personal Loan | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan | Not eligible | - | - | - | - | - | - |
| POONAWALLA | Poonawalla Instant Pl | Not eligible | - | - | - | - | - | - |
| NAVI | Navi Cash Loan | Not eligible | - | - | - | - | - | - |
| MONEYVIEW | Moneyview Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **KREDITBEE** (Preliminarily eligible): `REPRICED`, `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **HDFC** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **ICICI** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **AXIS** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **KOTAK** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **BOB** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`, `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **CANARA** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **UNION** (Not eligible): `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **INDUSIND** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **IDFC** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **YES** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE30`, `EXCESS_ENQUIRIES`
- **BAJAJ** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE60`
- **TATA** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SCORE_BELOW_MIN`, `RECENT_DPD_GTE60`
- **ABCL** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE60`
- **LNT** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE60`
- **POONAWALLA** (Not eligible): `SCORE_BELOW_MIN`, `RECENT_DPD_GTE60`
- **NAVI** (Not eligible): `SCORE_BELOW_MIN`
- **MONEYVIEW** (Not eligible): `SCORE_BELOW_MIN`

</details>

## EDGE03 — Existing EMI obligations already exceed a 50% FOIR threshold

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE03",
  "description": "Existing EMI obligations already exceed a 50% FOIR threshold",
  "date_of_birth": "1994-08-02",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 100000,
  "existing_monthly_emi": 55000,
  "card_outstanding": 50000,
  "has_credit_score": true,
  "bureau_score": 780,
  "total_experience_months": 96,
  "current_job_tenure_months": 48,
  "employer_category": "private_ltd",
  "city": "Ahmedabad",
  "salary_account_with": "icici",
  "requested_amount": 300000,
  "requested_tenure_months": 36
}
```

- Completed-years age: **32** (exact 32.2); bureau state: **valid**
- Products passing screening: **13/20**; covering the exact Rs 300,000 / 36m request: **0/20**
- Best option: **CANARA — Canara Budget** (Preliminarily eligible); APR 10.9%
  - Lowest APR (10.9%) among 12 eligible products offering the closest affordable alternative (the request is not fully covered); nominal rate 10.7%.
- Indicative-only (estimated APR): UNION

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| UNION | Union Professional Personal | Preliminarily eligible | Rs 9,675 | Rs 117,000 | 9.25-12.8% | 9.96%* | 54 | foir |
| CANARA | Canara Budget | Preliminarily eligible | Rs 9,779 | Rs 2,505,000 | 9.7-14.7% | 10.9% | 68 | foir |
| BOB | Baroda Personal Loan | Preliminarily eligible | Rs 9,924 | Rs 2,000,000 | 10.15-18.0% | 11.72% | 64 | product |
| HDFC | Hdfc Xpress Personal Loan | Preliminarily eligible | Rs 10,078 | Rs 110,000 | 9.99-24.0% | 12.79% | 54 | foir |
| IDFC | Idfc Firstmoney | Preliminarily eligible | Rs 10,078 | Rs 110,000 | 9.99-24.0% | 12.79% | 54 | foir |
| ICICI | Icici Personal Loan | Preliminarily eligible | Rs 9,863 | Rs 580,000 | 9.99-16.5% | 12.95% | 63 | calculator |
| YES | Yes Personal Loan | Preliminarily eligible | Rs 10,091 | Rs 124,000 | 10.85-21.0% | 14.99% | 54 | foir |
| NAVI | Navi Cash Loan | Preliminarily eligible | Rs 10,240 | Rs 133,000 | 9.9-29.96% | 16.03% | 54 | foir |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 10,136 | Rs 109,000 | 10.49-24.0% | 16.17% | 54 | foir |
| KOTAK | Kotak Personal Loan | Preliminarily eligible | Rs 10,194 | Rs 850,000 | 10.99-24.0% | 17.91% | 57 | calculator |
| POONAWALLA | Poonawalla Prime Pl | Preliminarily eligible | Rs 10,428 | Rs 104,000 | 9.99-36.0% | 18.65% | 54 | foir |
| KREDITBEE | Kreditbee Flexi Personal Loan | Preliminarily eligible | Rs 10,414 | Rs 104,000 | 12.0-27.5% | 19.19% | 54 | foir |
| MONEYVIEW | Moneyview Personal Loan | Preliminarily eligible | Rs 10,906 | Rs 97,000 | 14.0-36.0% | 20.13% | 54 | foir |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **UNION** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **CANARA** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **BOB** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **HDFC** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **IDFC** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **ICICI** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **YES** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **NAVI** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **INDUSIND** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **KOTAK** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **POONAWALLA** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **KREDITBEE** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **MONEYVIEW** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`
- **AXIS** (Not eligible): `AMOUNT_BELOW_MIN`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`
- **BAJAJ** (Not eligible): `AMOUNT_BELOW_MIN`
- **TATA** (Not eligible): `AMOUNT_BELOW_MIN`
- **ABCL** (Not eligible): `AMOUNT_BELOW_MIN`
- **LNT** (Not eligible): `AMOUNT_BELOW_MIN`

</details>

## EDGE04 — Changed jobs recently: four months with current employer

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE04",
  "description": "Changed jobs recently: four months with current employer",
  "date_of_birth": "1999-01-02",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 90000,
  "existing_monthly_emi": 5000,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 770,
  "total_experience_months": 36,
  "current_job_tenure_months": 4,
  "employer_category": "private_ltd",
  "city": "Pune",
  "salary_account_with": "none",
  "requested_amount": 500000,
  "requested_tenure_months": 36
}
```

- Completed-years age: **27** (exact 27.8); bureau state: **valid**
- Products passing screening: **11/20**; covering the exact Rs 500,000 / 36m request: **5/20**
- Best option: **IDFC — Idfc Firstmoney** (Eligible (requested terms)); APR 12.79%
  - Lowest APR (12.79%) among 5 eligible products covering the exact requested amount and tenure; nominal rate 12.79%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| IDFC | Idfc Firstmoney | Eligible (requested terms) | Rs 16,796 | Rs 1,500,000 | 9.99-24.0% | 12.79% | 71 | product |
| ICICI | Icici Personal Loan | Eligible (requested terms) | Rs 16,438 | Rs 2,690,000 | 9.99-16.5% | 12.95% | 72 | calculator |
| KOTAK | Kotak Personal Loan | Eligible (requested terms) | Rs 16,989 | Rs 1,700,000 | 10.99-24.0% | 17.91% | 71 | calculator |
| KREDITBEE | Kreditbee Flexi Personal Loan | Eligible (requested terms) | Rs 17,357 | Rs 1,000,000 | 12.0-27.5% | 17.99% | 70 | product |
| MONEYVIEW | Moneyview Personal Loan | Eligible (requested terms) | Rs 18,177 | Rs 1,000,000 | 14.0-36.0% | 20.13% | 70 | product |
| AXIS | Axis Personal Loan | Preliminarily eligible | Rs 16,493 | Rs 1,781,000 | 8.9-22.0% | 13.18% | 70 | foir |
| UNION | Union Women Professional | Preliminarily eligible | Rs 16,895 | Rs 1,800,000 | 12.0-18.0% | 13.2%* | 71 | multiple |
| YES | Yes Personal Loan | Preliminarily eligible | Rs 16,818 | Rs 1,800,000 | 10.85-21.0% | 14.99% | 71 | multiple |
| NAVI | Navi Cash Loan | Preliminarily eligible | Rs 17,067 | Rs 1,080,000 | 9.9-29.96% | 15.17% | 70 | multiple |
| BAJAJ | Bajaj Personal Loan | Preliminarily eligible | Rs 17,113 | Rs 1,620,000 | 10.0-30.5% | 17.66% | 71 | multiple |
| POONAWALLA | Poonawalla Prime Pl | Preliminarily eligible | Rs 17,379 | Rs 1,080,000 | 9.99-36.0% | 18.65% | 70 | multiple |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| BOB | Baroda Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| INDUSIND | Indusind Personal Loan | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **AXIS** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **UNION** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **YES** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **NAVI** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **BAJAJ** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **POONAWALLA** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`
- **HDFC** (Not eligible): `EXP_CURRENT_LT_MIN`
- **BOB** (Not eligible): `EXP_CURRENT_LT_MIN`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`
- **CANARA** (Not eligible): `EXP_CURRENT_LT_MIN`
- **INDUSIND** (Not eligible): `EXP_CURRENT_LT_MIN`
- **TATA** (Not eligible): `EXP_CURRENT_LT_MIN`
- **ABCL** (Not eligible): `EXP_CURRENT_LT_MIN`
- **LNT** (Not eligible): `EXP_CURRENT_LT_MIN`

</details>

## EDGE05 — Young applicant, eight months of experience, and no established credit history

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE05",
  "description": "Young applicant, eight months of experience, and no established credit history",
  "date_of_birth": "2005-07-15",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 30000,
  "existing_monthly_emi": 0,
  "card_outstanding": 0,
  "has_credit_score": false,
  "bureau_score": null,
  "total_experience_months": 8,
  "current_job_tenure_months": 8,
  "employer_category": "private_ltd",
  "city": "Surat",
  "salary_account_with": "none",
  "requested_amount": 100000,
  "requested_tenure_months": 24
}
```

- Completed-years age: **21** (exact 21.2); bureau state: **ntc**
- Products passing screening: **0/20**; covering the exact Rs 100,000 / 24m request: **0/20**
- Best option: **none** (no covering offer)
- Top blocking reasons: NTC_NOT_ALLOWED, EXP_TOTAL_LT_MIN, EXP_CURRENT_LT_MIN, SALARY_ACCOUNT_REQUIRED, EMPLOYER_NOT_ALLOWED

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| ICICI | Icici Personal Loan | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| BOB | Baroda Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| UNION | Union Personal All | Not eligible | - | - | - | - | - | - |
| INDUSIND | Indusind Personal Loan | Not eligible | - | - | - | - | - | - |
| IDFC | Idfc Firstmoney | Not eligible | - | - | - | - | - | - |
| YES | Yes Personal Loan | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan | Not eligible | - | - | - | - | - | - |
| POONAWALLA | Poonawalla Instant Pl | Not eligible | - | - | - | - | - | - |
| NAVI | Navi Cash Loan | Not eligible | - | - | - | - | - | - |
| KREDITBEE | Kreditbee Flexi Personal Loan | Not eligible | - | - | - | - | - | - |
| MONEYVIEW | Moneyview Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`
- **HDFC** (Not eligible): `EXP_TOTAL_LT_MIN`, `EXP_CURRENT_LT_MIN`, `NTC_NOT_ALLOWED`
- **ICICI** (Not eligible): `EXP_TOTAL_LT_MIN`, `NTC_NOT_ALLOWED`
- **AXIS** (Not eligible): `NTC_NOT_ALLOWED`
- **KOTAK** (Not eligible): `EXP_TOTAL_LT_MIN`, `NTC_NOT_ALLOWED`
- **BOB** (Not eligible): `EXP_CURRENT_LT_MIN`, `NTC_NOT_ALLOWED`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`, `EXP_TOTAL_LT_MIN`
- **CANARA** (Not eligible): `EXP_CURRENT_LT_MIN`, `NTC_NOT_ALLOWED`
- **UNION** (Not eligible): `AMOUNT_BELOW_MIN`
- **INDUSIND** (Not eligible): `EXP_TOTAL_LT_MIN`, `EXP_CURRENT_LT_MIN`, `NTC_NOT_ALLOWED`
- **IDFC** (Not eligible): `NTC_NOT_ALLOWED`, `EXP_TOTAL_LT_MIN`
- **YES** (Not eligible): `EXP_TOTAL_LT_MIN`, `NTC_NOT_ALLOWED`
- **BAJAJ** (Not eligible): `NTC_NOT_ALLOWED`, `EXP_TOTAL_LT_MIN`
- **TATA** (Not eligible): `EXP_TOTAL_LT_MIN`, `EXP_CURRENT_LT_MIN`, `NTC_NOT_ALLOWED`
- **ABCL** (Not eligible): `AGE_BELOW_MIN`, `EXP_TOTAL_LT_MIN`, `NTC_NOT_ALLOWED`
- **LNT** (Not eligible): `EXP_CURRENT_LT_MIN`, `EXP_TOTAL_LT_MIN`, `NTC_NOT_ALLOWED`
- **POONAWALLA** (Not eligible): `AGE_BELOW_MIN`, `NTC_NOT_ALLOWED`
- **NAVI** (Not eligible): `NTC_NOT_ALLOWED`
- **KREDITBEE** (Not eligible): `NTC_NOT_ALLOWED`
- **MONEYVIEW** (Not eligible): `NTC_NOT_ALLOWED`

</details>

## EDGE06 — Age 57 with a requested tenure of 60 months

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE06",
  "description": "Age 57 with a requested tenure of 60 months",
  "date_of_birth": "1969-01-10",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 150000,
  "existing_monthly_emi": 10000,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 790,
  "total_experience_months": 300,
  "current_job_tenure_months": 120,
  "employer_category": "private_ltd",
  "city": "Mumbai",
  "salary_account_with": "hdfc",
  "requested_amount": 600000,
  "requested_tenure_months": 60
}
```

- Completed-years age: **57** (exact 57.7); bureau state: **valid**
- Products passing screening: **17/20**; covering the exact Rs 600,000 / 60m request: **0/20**
- Best option: **CANARA — Canara Budget** (Eligible (alternative terms)); APR 10.97%
  - Lowest APR (10.97%) among 16 eligible products offering the closest affordable alternative (the request is not fully covered); nominal rate 10.7%.
- Indicative-only (estimated APR): UNION

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| CANARA | Canara Budget | Eligible (alternative terms) | Rs 12,956 | Rs 3,346,000 | 9.7-14.7% | 10.97% | 81 | foir |
| BOB | Baroda Personal Loan | Eligible (alternative terms) | Rs 13,262 | Rs 2,000,000 | 10.15-18.0% | 11.72% | 80 | product |
| ICICI | Icici Personal Loan | Eligible (alternative terms) | Rs 13,132 | Rs 4,420,000 | 9.99-16.5% | 13.45% | 81 | calculator |
| KREDITBEE | Kreditbee Flexi Personal Loan | Eligible (alternative terms) | Rs 14,305 | Rs 1,000,000 | 12.0-27.5% | 18.2% | 78 | product |
| KOTAK | Kotak Personal Loan | Eligible (alternative terms) | Rs 13,834 | Rs 2,800,000 | 10.99-24.0% | 19.2% | 80 | calculator |
| UNION | Union Professional Personal | Preliminarily eligible | Rs 12,736 | Rs 1,927,000 | 9.25-12.8% | 9.96%* | 80 | foir |
| HDFC | Hdfc Xpress Personal Loan | Preliminarily eligible | Rs 13,587 | Rs 1,868,000 | 9.99-24.0% | 12.79% | 87 | foir |
| IDFC | Idfc Higher Limit | Preliminarily eligible | Rs 13,587 | Rs 1,868,000 | 9.99-24.0% | 12.79% | 80 | foir |
| AXIS | Axis Personal Loan | Preliminarily eligible | Rs 13,202 | Rs 1,184,000 | 8.9-22.0% | 13.69% | 77 | foir |
| NAVI | Navi Cash Loan | Preliminarily eligible | Rs 13,933 | Rs 1,800,000 | 9.9-29.96% | 14.58% | 80 | multiple |
| YES | Yes Personal Loan | Preliminarily eligible | Rs 13,615 | Rs 1,866,000 | 10.85-21.0% | 15.62% | 80 | foir |
| BAJAJ | Bajaj Personal Loan | Preliminarily eligible | Rs 13,992 | Rs 2,700,000 | 10.0-30.5% | 16.37% | 80 | multiple |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 13,710 | Rs 1,860,000 | 10.49-24.0% | 17.06% | 80 | foir |
| ABCL | Abcl Personal Loan | Preliminarily eligible | Rs 14,083 | Rs 2,247,000 | 10.99-28.0% | 17.6% | 80 | foir |
| LNT | Lnt Personal Loan | Preliminarily eligible | Rs 13,713 | Rs 1,511,000 | 10.5-24.0% | 17.64% | 79 | foir |
| POONAWALLA | Poonawalla Regular Pl | Preliminarily eligible | Rs 14,334 | Rs 1,800,000 | 9.99-36.0% | 19.67% | 80 | multiple |
| TATA | Tata Personal Loan | Preliminarily eligible | Rs 14,397 | Rs 1,475,000 | 10.99-33.0% | 21.05% | 79 | foir |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| MONEYVIEW | Moneyview Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **CANARA** (Eligible (alternative terms)): `TENURE_NOT_SUPPORTED`
- **BOB** (Eligible (alternative terms)): `TENURE_NOT_SUPPORTED`
- **ICICI** (Eligible (alternative terms)): `TENURE_NOT_SUPPORTED`
- **KREDITBEE** (Eligible (alternative terms)): `TENURE_NOT_SUPPORTED`
- **KOTAK** (Eligible (alternative terms)): `TENURE_NOT_SUPPORTED`
- **UNION** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **HDFC** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **IDFC** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **AXIS** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **NAVI** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **YES** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **BAJAJ** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **INDUSIND** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **ABCL** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **LNT** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **POONAWALLA** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **TATA** (Preliminarily eligible): `TENURE_NOT_SUPPORTED`, `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`
- **MONEYVIEW** (Not eligible): `AGE_ABOVE_MAX`, `AGE_AT_MATURITY`

</details>

## EDGE07 — Established self-employed doctor with high income and strong credit

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE07",
  "description": "Established self-employed doctor with high income and strong credit",
  "date_of_birth": "1985-09-17",
  "application_date": "2026-10-11",
  "employment_type": "self_employed_professional",
  "net_monthly_income": 250000,
  "existing_monthly_emi": 5000,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 810,
  "total_experience_months": 180,
  "current_job_tenure_months": 120,
  "business_vintage_months": 120,
  "itr_years_available": 3,
  "employer_category": null,
  "city": "Ahmedabad",
  "salary_account_with": "none",
  "requested_amount": 2000000,
  "requested_tenure_months": 60
}
```

- Completed-years age: **41** (exact 41.1); bureau state: **valid**
- Products passing screening: **13/20**; covering the exact Rs 2,000,000 / 60m request: **2/20**
- Best option: **NAVI — Navi Cash Loan** (Eligible (requested terms)); APR 10.09%
  - Lowest APR (10.09%) among 2 eligible products covering the exact requested amount and tenure; nominal rate 9.9%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| NAVI | Navi Cash Loan | Eligible (requested terms) | Rs 42,396 | Rs 2,000,000 | 9.9-29.96% | 10.09% | 81 | product |
| LNT | Lnt Personal Loan Self Employed | Eligible (requested terms) | Rs 43,485 | Rs 3,000,000 | 11.0-18.0% | 13.13% | 83 | product |
| KREDITBEE | Kreditbee Flexi Personal Loan | Eligible (alternative terms) | Rs 44,489 | Rs 1,000,000 | 12.0-27.5% | 12.44% | 81 | product |
| MONEYVIEW | Moneyview Personal Loan | Eligible (alternative terms) | Rs 46,536 | Rs 1,000,000 | 14.0-36.0% | 15.08% | 81 | product |
| UNION | Union Professional Personal | Preliminarily eligible | Rs 41,857 | Rs 5,000,000 | 9.35-12.9% | 9.35%* | 84 | multiple |
| IDFC | Idfc Higher Limit | Preliminarily eligible | Rs 42,484 | Rs 5,000,000 | 9.99-24.0% | 9.99% | 84 | multiple |
| ABCL | Abcl Personal Loan Self Employed | Preliminarily eligible | Rs 43,475 | Rs 4,500,000 | 10.99-28.0% | 10.99% | 84 | multiple |
| ICICI | Icici Personal Loan | Preliminarily eligible | Rs 42,484 | Rs 5,000,000 | 9.99-16.5% | 11.03% | 84 | multiple |
| BOB | Baroda Personal Loan | Preliminarily eligible | Rs 44,489 | Rs 2,000,000 | 12.0-18.0% | 12.0%* | 81 | product |
| TATA | Tata Personal Loan | Preliminarily eligible | Rs 44,489 | Rs 4,500,000 | 12.0-18.0% | 12.0%* | 84 | multiple |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 42,978 | Rs 5,000,000 | 10.49-24.0% | 12.34% | 84 | multiple |
| PNB | Pnb Personal Loan Self Employed | Preliminarily eligible | Rs 44,489 | Rs 500,000 | 12.0-18.0% | 12.52%* | 81 | product |
| POONAWALLA | Poonawalla Professional Loan | Preliminarily eligible | Rs 45,506 | Rs 3,000,000 | 13.0-36.0% | 14.61% | 83 | multiple |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| YES | Yes Personal Loan | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan Self Employed | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **KREDITBEE** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **MONEYVIEW** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **UNION** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **IDFC** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **ABCL** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **ICICI** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **TATA** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **INDUSIND** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **PNB** (Preliminarily eligible): `AMOUNT_NOT_COVERED`
- **POONAWALLA** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SEGMENT_NOT_OFFERED`
- **HDFC** (Not eligible): `SEGMENT_NOT_OFFERED`
- **AXIS** (Not eligible): `SEGMENT_NOT_OFFERED`
- **KOTAK** (Not eligible): `SEGMENT_NOT_OFFERED`
- **CANARA** (Not eligible): `SEGMENT_NOT_OFFERED`
- **YES** (Not eligible): `SEGMENT_NOT_OFFERED`
- **BAJAJ** (Not eligible): `AMOUNT_BELOW_MIN`

</details>

## EDGE08 — Self-employed business owner with two-year business vintage and one ITR

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE08",
  "description": "Self-employed business owner with two-year business vintage and one ITR",
  "date_of_birth": "1989-02-14",
  "application_date": "2026-10-11",
  "employment_type": "self_employed_business",
  "net_monthly_income": 180000,
  "existing_monthly_emi": 20000,
  "card_outstanding": 100000,
  "has_credit_score": true,
  "bureau_score": 750,
  "total_experience_months": 60,
  "current_job_tenure_months": 24,
  "business_vintage_months": 24,
  "itr_years_available": 1,
  "employer_category": null,
  "city": "Surat",
  "salary_account_with": "none",
  "requested_amount": 1500000,
  "requested_tenure_months": 48
}
```

- Completed-years age: **37** (exact 37.7); bureau state: **valid**
- Products passing screening: **9/20**; covering the exact Rs 1,500,000 / 48m request: **0/20**
- Best option: **IDFC — Idfc Higher Limit** (Preliminarily eligible); APR 12.79%
  - Lowest APR (12.79%) among 5 eligible products offering the closest affordable alternative (the request is not fully covered); nominal rate 12.79%.
- Indicative-only (estimated APR): UNION, BOB, TATA, POONAWALLA

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| UNION | Union Personal Non Salaried | Preliminarily eligible | Rs 38,087 | Rs 1,500,000 | 9.35-12.9% | 10.37%* | 67 | product |
| IDFC | Idfc Higher Limit | Preliminarily eligible | Rs 40,085 | Rs 3,600,000 | 9.99-24.0% | 12.79% | 70 | multiple |
| BOB | Baroda Personal Loan | Preliminarily eligible | Rs 40,390 | Rs 2,000,000 | 12.0-18.0% | 13.2%* | 68 | product |
| TATA | Tata Personal Loan | Preliminarily eligible | Rs 40,390 | Rs 3,237,000 | 12.0-18.0% | 13.2%* | 69 | foir |
| NAVI | Navi Cash Loan | Preliminarily eligible | Rs 40,922 | Rs 2,000,000 | 9.9-29.96% | 14.23% | 68 | product |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 40,383 | Rs 3,600,000 | 10.49-24.0% | 15.49% | 70 | multiple |
| KREDITBEE | Kreditbee Flexi Personal Loan | Preliminarily eligible | Rs 41,822 | Rs 1,000,000 | 12.0-27.5% | 15.83% | 67 | product |
| MONEYVIEW | Moneyview Personal Loan | Preliminarily eligible | Rs 44,377 | Rs 1,000,000 | 14.0-36.0% | 19.75% | 67 | product |
| POONAWALLA | Poonawalla Instant Pl | Preliminarily eligible | Rs 45,646 | Rs 500,000 | 16.0-36.0% | 24.5%* | 67 | product |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| ICICI | Icici Personal Loan | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Personal Loan Self Employed | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| YES | Yes Personal Loan | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan Self Employed | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan Self Employed | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan Self Employed | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **UNION** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **IDFC** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `MAX_AMOUNT_ESTIMATED`
- **BOB** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **TATA** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `MAX_AMOUNT_ESTIMATED`
- **NAVI** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`
- **INDUSIND** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `MAX_AMOUNT_ESTIMATED`
- **KREDITBEE** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`
- **MONEYVIEW** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`
- **POONAWALLA** (Preliminarily eligible): `CARD_OUTSTANDING_UNKNOWN`, `AMOUNT_NOT_COVERED`, `TENURE_NOT_SUPPORTED`
- **SBI** (Not eligible): `SEGMENT_NOT_OFFERED`
- **HDFC** (Not eligible): `SEGMENT_NOT_OFFERED`
- **ICICI** (Not eligible): `ITR_YEARS_LT_MIN`
- **AXIS** (Not eligible): `SEGMENT_NOT_OFFERED`
- **KOTAK** (Not eligible): `SEGMENT_NOT_OFFERED`
- **PNB** (Not eligible): `SEGMENT_NOT_OFFERED`
- **CANARA** (Not eligible): `SEGMENT_NOT_OFFERED`
- **YES** (Not eligible): `SEGMENT_NOT_OFFERED`
- **BAJAJ** (Not eligible): `VINTAGE_LT_MIN`
- **ABCL** (Not eligible): `ITR_YEARS_LT_MIN`
- **LNT** (Not eligible): `ITR_YEARS_LT_MIN`

</details>

## EDGE09 — High-income applicant requesting a large personal loan of 50 lakh

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE09",
  "description": "High-income applicant requesting a large personal loan of 50 lakh",
  "date_of_birth": "1990-12-01",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 250000,
  "existing_monthly_emi": 0,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 820,
  "total_experience_months": 144,
  "current_job_tenure_months": 72,
  "employer_category": "mnc",
  "city": "Mumbai",
  "salary_account_with": "icici",
  "requested_amount": 5000000,
  "requested_tenure_months": 60
}
```

- Completed-years age: **35** (exact 35.9); bureau state: **valid**
- Products passing screening: **17/20**; covering the exact Rs 5,000,000 / 60m request: **3/20**
- Best option: **CANARA — Canara Budget** (Eligible (requested terms)); APR 9.73%
  - Lowest APR (9.73%) among 3 eligible products covering the exact requested amount and tenure; nominal rate 9.7%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| CANARA | Canara Budget | Eligible (requested terms) | Rs 105,499 | Rs 5,000,000 | 9.7-14.7% | 9.73% | 84 | product |
| ICICI | Icici Personal Loan | Eligible (requested terms) | Rs 106,211 | Rs 5,000,000 | 9.99-16.5% | 11.03% | 90 | calculator |
| KOTAK | Kotak Personal Loan | Eligible (requested terms) | Rs 108,687 | Rs 5,000,000 | 10.99-24.0% | 13.68% | 84 | calculator |
| NAVI | Navi Cash Loan | Eligible (alternative terms) | Rs 105,989 | Rs 2,000,000 | 9.9-29.96% | 9.98% | 84 | product |
| BOB | Baroda Personal Loan | Eligible (alternative terms) | Rs 106,605 | Rs 2,000,000 | 10.15-18.0% | 10.15% | 84 | product |
| KREDITBEE | Kreditbee Flexi Personal Loan | Eligible (alternative terms) | Rs 111,222 | Rs 1,000,000 | 12.0-27.5% | 12.18% | 84 | product |
| LNT | Lnt Personal Loan | Eligible (alternative terms) | Rs 107,470 | Rs 3,000,000 | 10.5-24.0% | 12.62% | 84 | product |
| MONEYVIEW | Moneyview Personal Loan | Eligible (alternative terms) | Rs 116,341 | Rs 1,000,000 | 14.0-36.0% | 15.08% | 84 | product |
| UNION | Union Professional Personal | Preliminarily eligible | Rs 104,399 | Rs 5,000,000 | 9.25-12.8% | 9.25%* | 84 | multiple |
| AXIS | Axis Personal Loan | Preliminarily eligible | Rs 103,549 | Rs 5,000,000 | 8.9-22.0% | 9.93% | 84 | multiple |
| HDFC | Hdfc Xpress Personal Loan | Preliminarily eligible | Rs 106,211 | Rs 5,000,000 | 9.99-24.0% | 9.99% | 84 | multiple |
| IDFC | Idfc Higher Limit | Preliminarily eligible | Rs 106,211 | Rs 5,000,000 | 9.99-24.0% | 9.99% | 84 | multiple |
| POONAWALLA | Poonawalla Prime Pl | Preliminarily eligible | Rs 106,211 | Rs 3,000,000 | 9.99-36.0% | 12.1% | 84 | multiple |
| YES | Yes Personal Loan | Preliminarily eligible | Rs 108,338 | Rs 5,000,000 | 10.85-21.0% | 12.16% | 84 | multiple |
| BAJAJ | Bajaj Personal Loan | Preliminarily eligible | Rs 106,235 | Rs 4,500,000 | 10.0-30.5% | 12.18% | 84 | multiple |
| INDUSIND | Indusind Personal Loan | Preliminarily eligible | Rs 107,445 | Rs 5,000,000 | 10.49-24.0% | 12.34% | 84 | multiple |
| ABCL | Abcl Personal Loan | Preliminarily eligible | Rs 108,687 | Rs 4,500,000 | 10.99-28.0% | 13.12% | 84 | multiple |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **NAVI** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **BOB** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **KREDITBEE** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **LNT** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **MONEYVIEW** (Eligible (alternative terms)): `AMOUNT_NOT_COVERED`
- **UNION** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **AXIS** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **HDFC** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **IDFC** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **POONAWALLA** (Preliminarily eligible): `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **YES** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **BAJAJ** (Preliminarily eligible): `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **INDUSIND** (Preliminarily eligible): `MAX_AMOUNT_ESTIMATED`
- **ABCL** (Preliminarily eligible): `AMOUNT_NOT_COVERED`, `MAX_AMOUNT_ESTIMATED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`
- **TATA** (Not eligible): `EMPLOYER_NOT_ALLOWED`

</details>

## EDGE10 — Good credit score but a loan settlement occurred 18 months ago

**Input (canonical fields):**

```json
{
  "profile_id": "EDGE10",
  "description": "Good credit score but a loan settlement occurred 18 months ago",
  "date_of_birth": "1988-08-20",
  "application_date": "2026-10-11",
  "employment_type": "salaried",
  "net_monthly_income": 120000,
  "existing_monthly_emi": 10000,
  "card_outstanding": 0,
  "has_credit_score": true,
  "bureau_score": 720,
  "has_settled_loan": true,
  "settled_loan_months_ago": 18,
  "write_off_flag": false,
  "total_experience_months": 120,
  "current_job_tenure_months": 60,
  "employer_category": "private_ltd",
  "city": "Pune",
  "salary_account_with": "none",
  "requested_amount": 500000,
  "requested_tenure_months": 36
}
```

- Completed-years age: **38** (exact 38.1); bureau state: **valid**
- Products passing screening: **1/20**; covering the exact Rs 500,000 / 36m request: **0/20**
- Best option: **KREDITBEE — Kreditbee Flexi Personal Loan** (Preliminarily eligible); APR 27.03%
  - Lowest APR (27.03%) among 1 eligible products offering the closest affordable alternative (the request is not fully covered); nominal rate 23.98%.

| Lender | Product | Status | Requested EMI | Max eligible | Rate | APR | Fit | Binding cap |
|---|---|---|---|---|---|---|---|---|
| KREDITBEE | Kreditbee Flexi Personal Loan | Preliminarily eligible | Rs 19,611 | Rs 400,000 | 12.0-27.5% | 27.03% | 50 | product |
| SBI | Sbi Personal Loan Salary Package | Not eligible | - | - | - | - | - | - |
| HDFC | Hdfc Xpress Personal Loan | Not eligible | - | - | - | - | - | - |
| ICICI | Icici Personal Loan | Not eligible | - | - | - | - | - | - |
| AXIS | Axis Personal Loan | Not eligible | - | - | - | - | - | - |
| KOTAK | Kotak Personal Loan | Not eligible | - | - | - | - | - | - |
| BOB | Baroda Personal Loan | Not eligible | - | - | - | - | - | - |
| PNB | Pnb Sahyog Rin Personal Loan Public | Not eligible | - | - | - | - | - | - |
| CANARA | Canara Budget | Not eligible | - | - | - | - | - | - |
| UNION | Union Personal All | Not eligible | - | - | - | - | - | - |
| INDUSIND | Indusind Personal Loan | Not eligible | - | - | - | - | - | - |
| IDFC | Idfc Firstmoney | Not eligible | - | - | - | - | - | - |
| YES | Yes Personal Loan | Not eligible | - | - | - | - | - | - |
| BAJAJ | Bajaj Personal Loan | Not eligible | - | - | - | - | - | - |
| TATA | Tata Personal Loan | Not eligible | - | - | - | - | - | - |
| ABCL | Abcl Personal Loan | Not eligible | - | - | - | - | - | - |
| LNT | Lnt Personal Loan | Not eligible | - | - | - | - | - | - |
| POONAWALLA | Poonawalla Instant Pl | Not eligible | - | - | - | - | - | - |
| NAVI | Navi Cash Loan | Not eligible | - | - | - | - | - | - |
| MONEYVIEW | Moneyview Personal Loan | Not eligible | - | - | - | - | - | - |

<details><summary>Reason codes for non-covering / flagged products</summary>

- **KREDITBEE** (Preliminarily eligible): `REPRICED`, `AMOUNT_NOT_COVERED`
- **SBI** (Not eligible): `SALARY_ACCOUNT_REQUIRED`, `EMPLOYER_NOT_ALLOWED`, `PRIOR_WRITEOFF_SETTLEMENT`
- **HDFC** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **ICICI** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **AXIS** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **KOTAK** (Not eligible): `SCORE_BELOW_MIN`, `PRIOR_WRITEOFF_SETTLEMENT`
- **BOB** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **PNB** (Not eligible): `EMPLOYER_NOT_ALLOWED`, `SALARY_ACCOUNT_REQUIRED`, `PRIOR_WRITEOFF_SETTLEMENT`
- **CANARA** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **UNION** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **INDUSIND** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **IDFC** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **YES** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **BAJAJ** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **TATA** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **ABCL** (Not eligible): `SCORE_BELOW_MIN`, `PRIOR_WRITEOFF_SETTLEMENT`
- **LNT** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **POONAWALLA** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **NAVI** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`
- **MONEYVIEW** (Not eligible): `PRIOR_WRITEOFF_SETTLEMENT`

</details>
