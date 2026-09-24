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

## Retention score (September 23 approved extension)

The owner approved a 30% retained-freight target and a 28% acceptable floor. The score is a **period management contribution**, not book profit or the as-of amount safe to withdraw.

- Retained per $100 = recorded retained contribution / positive freight revenue × 100.
- Score = retained per $100 / target percent × 100. Target attainment is 100; better results can exceed 100 and losses remain negative. Zero/negative freight produces no score.
- Status uses the unrounded ratio: 30% meets target, 28% is acceptable, below 28% is below acceptable. Display rounding cannot change the band.
- The bridge starts with statement remainder, adds net outside recorded costs/income (including accrued interest), adds the freight-proportional company result, subtracts business-paid equipment obligations and new positive non-opening repair/capital funding, and restores repair costs already covered by protected funds. Book depreciation and equipment disposal are excluded from this freight-performance measure.
- Company amounts are allocated for comparison only, using exact cents and largest remainders with asset ID tie breaking. The ledger still records each company cost once. Period scores use period totals, never averages of weekly percentages. Allocation can change as the period's freight mix changes.
- Repair offset = reserves consumed by payments during the period + change in funded coverage of unpaid claims. This prevents a covered incurred repair, its later payment, a personal-payment substitution and reimbursement from becoming repeated retention costs. Discretionary reserve releases do not become earnings.
- A supporting HELOC principal record never duplicates its linked payment. Personal HELOC uses do not enter the calculation. Equipment card repayment attribution and operational effects of reversals remain explicit review gaps.
- Targets are immutable dated events, with positive acceptable <= target <= 100. Backdating is rejected. Each report uses the benchmark effective at its start. Settings use the confirmed business timezone, or explicitly labeled UTC until setup; the form receives its minimum date from the server. Future changes remain visible in target history.

All scores currently remain **provisional**: there is no per-period completeness attestation yet. Unfunded reserve targets and scheduled financing obligations are not silently treated as funded deductions. The expanded calculation explicitly requires outside-cost reconciliation, target funding and financing verification. It cannot be used as confirmed take-home pay. Driver names are current equipment labels; historical driver attribution still requires dated driver assignments. Unassigned equipment results remain visible review gaps.

Worked cases: $30 retained from $100 → 100; $28 → 93.33 acceptable; $25 → 83.33 below floor; $33 → 110; -$3 → -10. An opening $1,000 reserve covering a $500 repair leaves current retained contribution unchanged whether unpaid, paid in the same period or paid next period. Funding a new $1,000 reserve reduces period contribution by $1,000 once, including when $500 of it covers a repair. A $1,000 business equipment reimbursement reduces contribution once even when a matching HELOC schedule row also exists.
