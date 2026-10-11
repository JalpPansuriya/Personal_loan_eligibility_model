# Phase 8 — Targeted re-verification (2026-10-11)

Live re-check of the four lenders plan2 flagged plus the applicable RBI guidance. The
other 16 lenders were re-audited against the cached official pages already in this folder
(all captured 2026-10-10, URLs + access dates preserved in `data/lender_rules_long.csv`).
Nothing here changes a stored value unless noted; it records the evidence and any conflict.

## SBI — SBI Personal Loan / Xpress Credit (salary package)
- Official FAQ: "Maximum Loan amount: Rs. 50.00 lakhs subject to 30 times Net Monthly
  Income (NMI), applicable EMI/NMI ratio (upto 65%)."
  https://sbi.co.in/web/faq-s/faq-personal-loan/ (verified 2026-10-11)
- Stored cap `loan_max = 5,000,000` (₹50L) — CONSISTENT.
- Conflict: secondary aggregators cite ₹35L / 24× NMI for a narrower Xpress Credit variant.
  We model the published ₹50L / 30× salary-package product; the ₹35L figure is a different
  scheme and is NOT merged in (plan2: do not combine SBI products into a fictional one).

## Canara — Canara Budget (prime / delight)
- Official canara-budget page (cached 2026-10-10): Prime 25× gross salary, max ₹50L;
  Delight 25× gross salary, max ₹40L; "higher quantum also can be considered selectively";
  net take-home ≥ max(25% of net, ₹10,000) after all instalments; tenure ≤ 84m.
- Stored caps `loan_max` 50L (prime) / 40L (delight) now BIND (Phase 4 fix). The "selective"
  higher quantum is flagged as a non-automatic exception, never applied.
- Conflict: some aggregators cite ₹10L / ₹20L and 6× for a different Canara product (not
  Canara Budget). Not applied; recorded as a cross-source conflict.

## Union — multiple products
- Women Professional / SRLGE (govt): published ₹50L / ₹25L caps — stored and bind.
- Non-salaried (SEB): published ₹5L (new) / ₹15L (existing, 24m record) — stored.
- `union_personal_salaried_pvt` and `union_professional_personal`: the official product
  pages render tab headings only (tab bodies absent in capture), so NO published amount cap
  could be established. These remain an ESTIMATED 20× multiple with NO published loan_max;
  the engine flags such sizing as MAX_AMOUNT_ESTIMATED / PRELIMINARILY_ELIGIBLE rather than
  presenting a precise figure (plan2: do not manufacture a cap).

## PNB — Personal Loan Scheme for Public
- Public scheme published max ₹20L (verified via official page + aggregators 2026-10-11);
  distinct doctor/professional route has its own income-history + residence conditions.
  https://www.pnb.bank.in/personalloanforpublic.html (cached 2026-10-10)
- Stored cap `loan_max = 2,000,000` (₹20L) — CONSISTENT.

## RBI — Key Facts Statement (KFS) & Digital Lending Directions, 2025
- KFS circular (RBI/2024-25, effective for loans sanctioned on/after 1 Oct 2024) mandates a
  standardised Key Facts Statement disclosing the all-in cost as an Annual Percentage Rate
  (APR), computed on actual borrower cash flows (fees netted at disbursal).
  https://website.rbi.org.in/documents/87730/39710850/Circular+KFS_180424_Final_For_Website.pdf
- Digital Lending Directions, 2025 require the KFS to be shown before borrower acceptance,
  with a cooling-off period and grievance channels.
- Applicability to THIS app: it is a non-transacting comparison/estimation tool; it does not
  originate loans, so it is not itself a Regulated Entity/LSP under the DLD. We nonetheless
  adopt the KFS design objectives as best practice: APR as an IRR on net cash flows, costs
  shown separately (rate / fee / GST / net disbursal / total), published vs estimated rates
  distinguished, and no approval claims. This is a design conclusion, not legal advice.

## Method note
- Primary = official lender/regulator pages (cached in this folder, 2026-10-10, re-checked
  2026-10-11 for the four above). Secondary aggregators used only to triangulate and are
  labelled as conflicts where they disagree.
- Where a page could not establish a value (Union pvt/professional caps), the rule stays
  ESTIMATED and the engine surfaces it as such; no value was fabricated.
