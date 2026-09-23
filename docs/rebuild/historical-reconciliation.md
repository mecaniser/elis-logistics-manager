# Historical settlement reconciliation — local milestone

Snapshot: September 23, 2026. Production was read only. Source bytes, the authenticated record snapshot and the isolated review database are retained locally in the git-ignored `backend/settlements_extracted/rebuild-20260923/` directory. No historical production values were overwritten.

## Coverage and scope

- 212 saved settlement records inventoried: 175 source records and 37 derived trailer allocations.
- Source record dates: December 14, 2024 through September 21, 2026. These include seven manual trailer records, not 175 original PDFs.
- 78 original PDFs retrieved and preserved with SHA-256 hashes and extracted page text: 37 of the 77 Cargo layout and 41 of the 277 paystub layout.
- 77 originals pass the normalized arithmetic checks. One source has ambiguous row-column values that require review. Arithmetic matching is not proof of bank deposit, driver receipt, complete expenses or finalized accrual books.
- 97 records lack a retrievable original: 90 old local-file references returned unavailable from the existing upload location, and seven manual entries never referenced a PDF. These remain visible, with stored figures labeled unverified.
- Only the two September 21 statements have been posted to the isolated review ledger. The remaining historical analysis is read only. Periods with unposted records explicitly show incomplete coverage.

## What was implemented

`GET /api/v1/accounting/settlement-history` applies the existing server-derived business authorization. Each record carries its date, scope, evidence status, original reference, arithmetic difference, saved/source differences, driver deduction, load rows, reported mileage basis, purchased gallons when present, and investigation items. Exact original downloads retain tenant checks.

The review checks payout arithmetic, load freight totals, fuel detail totals for normalized 77 Cargo sources, repeated sources/load IDs, future delivery dates, row mileage coverage, driver-share changes, rolling fuel spending and unusual other deductions. Expected internal reserve allocations and modeled interest are distinguished from unexplained changes.

Rolling fuel-spending comparisons use the same truck and carrier, weighted fuel dollars divided by reported miles over 28 calendar days, compared with the previous 28-day window. A window needs at least three qualifying statements and excludes unverified/estimated distance. A rise over 10% is an investigation signal. It is not measured consumption, a fuel-theft conclusion or an estimate of proven recoverable loss. Overlapping windows must not be summed.

Other-charge flags require at least four recent same-truck/carrier statements, more than 50% above the recent median and at least $100 above it. Driver-share flags use a greater-than-two-percentage-point deviation from the prior median. These are transparent review heuristics, not contractual overpayment tests.

## September 21 source reconciliation

| Statement item | Truck 603 | Truck 609 | Combined |
|---|---:|---:|---:|
| Original freight | $11,800.00 | $11,900.00 | $23,700.00 |
| Carrier retention | $1,416.00 | $1,428.00 | $2,844.00 |
| Driver deduction | $3,540.00 | $3,570.00 | $7,110.00 |
| Fuel purchases | $2,811.94 | $4,032.89 | $6,844.83 |
| Insurance | $300.00 | $300.00 | $600.00 |
| Tolls | $54.72 | $209.53 | $264.25 |
| Support | $0.00 | $200.00 | $200.00 |
| Statement remainder | $3,677.34 | $2,159.58 | $5,836.92 |

The $1,517.76 lower remainder for 609 is exactly explained by $1,220.95 more fuel, $200 support, $154.81 more tolls, $30 more driver pay and $12 more carrier retention, offset by $100 more freight. Fuel spending per reported mile is $1.100 versus $0.903, a 21.86% difference using unrounded ratios. Statement mileages are 3,665 and 3,114; different routes and purchase timing preclude a consumption conclusion.

The legacy business display of $5,155.20 differs from the $5,836.92 statement remainder by $600 of repair planning allocations and $81.72 of modeled financing interest. Internal trailer allocations of $800 cancel at company level. This is an explained change of definition; it does not establish newly available cash. The old displayed aggregate expense omitted the $200 support charge while stored settlement deductions included it. The corrected source breakdown includes it exactly once.

The 609 PDF includes load 5073 with delivery September 23 on a September 21 statement. It requires service-date review before finalizing accrual period earnings. All 13 fuel rows across the two PDFs leave diesel/other-product classification unconfirmed.

## Historical findings requiring follow-through

1. Twenty-one stored records have freight $200 higher than the corresponding PDF: a $4,200 difference in reporting, not a proved cash loss. For March 7, the PDF payout is -$97.70 while the saved net is $89.85; $200 additional recorded freight less $12.45 modeled interest explains that difference. For March 14, stored freight is $4,149.95 versus $3,949.95 in the original, and stored net is $758.87 versus $558.87 source payout. Identify the historical adjustment mechanism and supporting evidence before accepting or correcting it.
2. The November 29, 2025 source has $550 in a fuel row, a blank driver-pay row cell and $0 fuel in its summary. Normalized text cannot safely assign the shifted columns; the source remains under review. The original was visually inspected. This is a source/row inconsistency, not evidence that a driver received $550.
3. Twelve rolling fuel-spending windows exceed the 10% review threshold. These overlap and must not be summed. The September 21 window for 609 is 11.5% above its preceding window; prices, routes, timing and mileage coverage remain possible explanations.
4. Four sources show delivery after statement date. Twenty-eight other-charge signals and 23 driver-share signals need agreement/invoice context. These are candidates for investigation, not verified errors.
5. Category remapping (for example deduct versus prepass), internal repair targets and modeled interest account for some saved/source differences. The field-level register preserves them without rewriting earlier interpretations.

## Remaining acceptance work

Recover missing originals from backups or owner records; reconcile statements and driver payments to bank/card evidence; check carrier agreements and unusual deductions; incorporate actual repair/invoice/payment evidence; reconcile independent Motive/odometer intervals and classified diesel purchases. Complete accounting policy, opening balances and HELOC tracing before final books or withdrawal figures. The original six-stage plan remains open; see `execution-tracker.md`.
