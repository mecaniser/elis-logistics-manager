# ELIS finance definitions and migration contract

The financial foundation and workflows for the owner-approved plan are implemented in an additive v1 accounting workspace. Historical reconstruction and production cutover remain gated on real source records. Legacy records remain source candidates, never opening balances or posted v1 facts. USD money uses decimal strings and decimal arithmetic.

| Metric | Definition | Required evidence |
|---|---|---|
| Available to owner | Reconciled business bank cash less funded repair/capital earmarks, uncovered vendor/owner claims, card obligations and unique committed financing obligations | Complete account list, as-of statements, linked claims and payments |
| Settlement remainder | Original freight less carrier retention and all operating deductions, before internal reserve/trailer allocations | Reconciled settlement source |
| Operating earnings | Accrued revenue less incurred operating costs, before interest, book depreciation and equipment disposal gains/losses | Posted journal and policy |
| Net income | Operating earnings less interest and book depreciation plus disposal gains/losses | Posted journal |
| Calendar-day earnings | Period net income / inclusive calendar days | One shared period, including downtime |
| Expense ratio | Expense / original freight gross | Identical numerator and denominator period |
| Capital target | Max(acquisition cost minus expected net resale proceeds, zero) | Acquisition and sale assumptions |
| Funded reserve | Explicit confirmed cash earmarks less releases and funded repairs | Bank coverage and allocation evidence |
| Required weekly capital funding | Remaining target × 7 / remaining calendar days | Current dated plan; overdue shown separately |
| Measured MPG | Independently measured miles / supported consumed diesel gallons over the same interval | Independent distance and consumption evidence |
| Miles per gallon purchased | Complete 28-day independent distance / diesel gallons purchased in that window | 28-day coverage; fuel timing caveat |
| Lifetime equipment profit | Operating/interest result before depreciation and disposal gain − acquisition + actual net sale proceeds | Complete ownership history |

## Worked acceptance examples

- $23,700 freight − $2,844 carrier − $7,110 drivers − $6,844.83 fuel − $600 insurance − $264.25 tolls − $200 support = $5,836.92 settlement remainder. Trailer splits and reserve allocations do not reduce company operating earnings.
- Bank cash $10,000, repair reserve $1,000: available $9,000. Incur a $500 bill covered by that reserve: available remains $9,000. Pay it: bank $9,500, reserve $500, available still $9,000.
- Owner pays the vendor bill: vendor claim clears and owner claim replaces it. One repair expense, one remaining reimbursement obligation.
- Card charge clears the vendor bill and creates card liability. Card repayment clears liability and cash. Expense is recognized only on the original bill.
- A $50,000 acquisition with $20,000 expected resale needs $30,000 protected capital. Expected resale is not bank cash. Acquisition and principal repayment cannot create duplicate owner reimbursement claims.
- A 22% fuel-cost-per-mile difference is a review signal. It is not measured consumption or proof of misconduct.

## Rollout

New data uses separate tables. Read-only legacy comparison explains allocation/interest differences and labels legacy mileage unverified. Never infer funded reserves or payoff from historical profit. Opening journals, account coverage, policies, and historical completeness require source confirmation. The new workspace is available at `/finance`; the existing home remains at `/` until reconciliation and browser acceptance authorize cutover.
