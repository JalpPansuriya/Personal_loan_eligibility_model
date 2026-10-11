# Rule extraction spec (for building data/rules/{lender}.csv)

Output: one CSV per lender at `data/rules/{lender_id}.csv`, UTF-8, comma-separated, RFC-4180 quoting (wrap any field containing a comma, quote or newline in double quotes; escape internal double quotes by doubling them).

## Columns (exact header, this order)

```
rule_id,lender_id,product,segment,variable,operator,value,unit,effect,condition,source_url,source_file,accessed_date,confidence,estimation_method,quote,notes
```

| column | allowed values / format |
|---|---|
| rule_id | `{lender_id}-{NNN}`, e.g. `sbi-001`, sequential |
| lender_id | one of: sbi hdfc icici axis kotak bob pnb canara union indusind idfc yes bajaj tata abcl lnt poonawalla navi kreditbee moneyview |
| product | short product slug as the lender names it, e.g. `sbi_personal_loan_salary_package`, `union_professional_personal`, `idfc_firstmoney`, `poonawalla_instant` |
| segment | `salaried` \| `sep` (self-employed professional) \| `seb` (self-employed business) \| `all` |
| variable | one of the controlled vocabulary below |
| operator | `>=` `<=` `>` `<` `==` `in` `not_offered` `range` `formula` `grid` `info` |
| value | number (no commas, no ₹; percentages as numbers e.g. `65` with unit `pct`), or a list `a|b|c` for `in`, or `min..max` for `range`, or a short expression for `formula`, or a grid reference file name for `grid` |
| unit | `years` `months` `inr_per_month` `inr_per_year` `inr` `pct` `pct_pa` `score` `count` `x_income` `bool` `text` |
| effect | `gate` (hard eligibility) \| `amount_cap` \| `foir` \| `multiple` \| `rate` \| `tenure` \| `fee` \| `pricing_modifier` \| `info` |
| condition | free text condition under which the rule applies (e.g. `employer_category in govt|defence`, `city_tier==metro`, `loan_amount>200000`), or empty |
| source_url | exact URL from the snapshot header (or from data/sources/index.csv for PDFs) |
| source_file | snapshot file name in data/sources/ (for PDFs use the .txt extraction file name) |
| accessed_date | `2026-10-10` |
| confidence | `published` (lender's own page states it) \| `published_conflict` (lender's own pages disagree — emit one row per variant) \| `derived` (computed from published numbers; explain in estimation_method) \| `estimated` (not published; default/assumption) |
| estimation_method | required when confidence is `derived` or `estimated`, else empty |
| quote | EXACT verbatim substring copied from the snapshot file (whitespace may be collapsed but no words changed, ≤ 300 chars). Required for `published`/`published_conflict`. Empty for `estimated`. |
| notes | short free text |

## Controlled vocabulary for `variable`

Eligibility gates:
`segment_offered`, `age_min`, `age_max_at_application`, `age_max_at_maturity`, `income_min_monthly`, `income_min_annual`, `household_income_min_annual`, `household_income_min_monthly`, `exp_total_min_months`, `exp_current_min_months`, `business_vintage_min_months`, `post_qualification_exp_min_months`, `itr_years_min`, `score_min`, `score_preferred`, `ntc_allowed`, `employer_category_allowed`, `profession_allowed`, `salary_account_required`, `relationship_min_months`, `residence_stability_min_months`, `city_serviced`, `nationality`, `education_min`, `co_applicant_required`, `guarantor_required`, `max_active_loans`

Sizing:
`foir_max`, `take_home_floor`, `income_multiple_max`, `loan_min`, `loan_max`, `tenure_min_months`, `tenure_max_months`

Pricing:
`rate_min_pa`, `rate_max_pa`, `rate_mean_pa`, `rate_grid`, `rate_benchmark`, `apr_min`, `apr_max`, `processing_fee_pct`, `processing_fee_min_inr`, `processing_fee_max_inr`, `processing_fee_flat_inr`, `processing_fee_waiver`, `gst_on_fee`, `documentation_fee_inr`

Info only (not used by engine, but record if clearly stated): `foreclosure`, `penal_charge`, `bounce_charge`, `lending_entity`

## Rules for the extractor

1. Read ONLY the local snapshot files given to you (data/sources/*.md and *.txt). Do not browse the web. Do not use memory.
2. Every `published` row MUST have a `quote` that is an exact substring of the named `source_file` (you may collapse runs of whitespace/newlines to a single space, nothing else). If you cannot find exact supporting text, do NOT mark it published.
3. If the lender's own pages disagree on a value, emit one row per variant with `confidence=published_conflict`, each with its own quote and source_file, and note the conflict in `notes`.
4. If a segment is not offered for personal loans, emit `variable=segment_offered, operator=not_offered` with the supporting quote.
5. Record rate grids (score bands × employer category etc.) as separate rows using `variable=rate_grid`, `operator=grid`, `value=<band description>=<rate>` — one row per cell — e.g. `value=score>=800=9.30`, `condition=scheme==salaried_pvt; benchmark EBLR 8.25`. Keep the quote to the row/cell text.
6. Generic explainer text ("most lenders cap FOIR at 50-55%") is NOT a lender rule. If that is the only FOIR/multiple text, record it with `confidence=estimated`, `estimation_method=generic explainer text on lender page, not stated as lender policy`, and put the generic sentence in `notes` (not quote).
7. For anything the engine needs but the snapshots do not state (e.g. FOIR, income multiple, NTC policy, max age at maturity), emit ONE row with `confidence=estimated`, empty quote, and `estimation_method` exactly as instructed in your task prompt (defaults given there).
8. Do not invent numbers. Do not round published numbers.
9. Return in your final message: count of rows by confidence, list of conflicts found, list of variables left estimated, and any snapshot that seemed truncated/missing content.
