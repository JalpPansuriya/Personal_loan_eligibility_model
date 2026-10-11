## The problem

A person asks: "Can I get a personal loan, and from whom?" Banks do not publish their full eligibility rules. They publish some of them, such as minimum age, minimum salary and a CIBIL cut-off. The other rules show up in calculators, FAQs, product terms, RBI rules and loan-comparison sites.

Your job is to find the rules that decide personal loan eligibility in India, turn them into datapoints, and build a simple model. The model takes one person's profile and returns a decision.

## Scope

- Personal loans only. Do not include other loan types.  
- Cover the top 20 personal loan lenders in India. Choose the list yourself, and explain how you chose it. You can include banks, NBFCs and fintech lenders.  
- Use public sources only. Do not use customer data or data that needs a login.  
- Use current rules. Record the date when you read each source.

## What to do

1. **Find the rules.** For each lender, collect every rule that affects eligibility, the loan amount, the rate or the tenure. Examples are age, income, job type, employer category, work experience, city, credit score, existing EMIs, FOIR and the maximum multiple of salary. A listed rule is not enough. Find the rules that are not listed. Calculators, rate bands, FAQs and lender terms can show them.  
2. **Build the datapoint set.** Make one table of the input variables that the model needs. Give each variable a name, a unit, a type and a description. Also say where each value comes from: the bureau, the applicant, or a document.  
3. **Build the lender rule table.** Make one row for each lender. Give each rule a value, a source link and a date. If you estimated a value, mark it as an estimate and explain how you got it.  
4. **Build the model.** It can be rule-based or a scorecard. Do not train an ML model, because there is no approval data. For each person, the model must do this:  
   - Decide whether the person is eligible or not eligible. If not eligible, give the reason.  
   - If the person is eligible, return the lenders that would approve the loan. For each lender, give the maximum loan amount, the expected interest rate and the possible tenure.  
   - Show the best option and explain why it is the best.  
5. **Test it.** Make at least 10 sample profiles. Include edge cases, such as a low score, a high existing EMI, a new job, self-employed, or an age near the limit. Show the output for each profile.

## What to submit

Submit a link to a GitHub repo. The repo must contain:

- The input variables and their definitions.  
- The rules for the 20 lenders, with a source and a date for each rule.  
- The model code.  
- Test profiles and the output for each profile.  
- `README.md` with:  
  - how you chose the lenders  
  - your approach  
  - the assumptions you made, and how you found the rules that are not listed  
  - insights, for example which rule fails the most applicants or how lenders differ  
  - the limits of your model and what you would add next

