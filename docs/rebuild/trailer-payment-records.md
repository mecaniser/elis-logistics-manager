# Trailer payment records

The trailer page leads with borrowed (or cash invested), principal paid from matched bank records (or estimated cash recovery), and estimated free cash. Monthly and sale forecasts, calculation details and settlement rows are closed by default. Previous ROI calculations remain available separately.

## User journey

1. Save the existing trailer investment plan, including only this trailer's borrowed amount.
2. Open **Record / review payments** on the trailer, or **Trailer payments** in Bank Monitor.
3. Set the next statement due date and planned payment, attaching its supporting lender statement. This does not create a payment or a bank transfer.
4. Pay at the bank. A separate debit makes the trailer's payment identifiable. ELIS's trailer share does not create a separate lender subaccount.
5. Import the paying bank account's posted CSV statement if its debit is not already in Finance. Reuse the same bank account. The opening balance, transactions and closing balance must reconcile.
6. Select the dedicated debit, enter principal and interest, attach the lender statement, and describe how the trailer's interest share was determined. Confirm the split. The complete debit must belong to this trailer; mixed-purpose payments are deliberately not guessed or auto-split.
7. Review the saved payment, bank reference and original statement. To fix an error, remove its match with a reason and record the corrected match. Both events remain in the audit trail; corrected historical views exclude the voided match.

## Calculation and evidence boundaries

- Only matched principal reduces **Principal paid off**. Interest is separate. No matched records means **Not confirmed**, not zero paid.
- Borrowing less recorded principal is the tracked trailer share, not a confirmed lender balance. Missing payments, fees and borrowing changes require review.
- Historical free cash estimate = saved trailer income − larger of settlement repayment budget / matched payments − planned personal cash recovery − repairs in the repair register. Missing other costs and taxes can reduce it.
- Finance uses payments on their posted dates. Matched payments replace that period's budget up to the budget amount; amounts above it reduce estimated cash once. Period estimates mix dated cash payments and calendar budgets, so adjacent periods need not sum to a larger period when payment timing differs. Payments with no unique truck pairing reduce the unassigned business result.
- A due-date record is a reminder in the application, not an external scheduled payment. The saved investment plan continues to control forecasts.
- This register uses uploaded bank statements, not an automatic Plaid transaction import. It does not initiate bank transfers.
- These are management payment records. They do not silently post acquisition/loan journals or discharge an unrelated owner-reimbursement claim. Formal Accounting remains separately reconciled; readiness explicitly marks the payment register's loan-journal review incomplete.

## Implementation and safeguards

Uses immutable, tenant-scoped Finance events: `equipment_payment_due`, `equipment_payment`, `equipment_payment_void`. Original evidence is retained by FinanceEvidence. No schema migration is required.

Payment writes share the finance business lock, idempotency and closed-period controls. Validation checks asset ownership, a saved financing plan, source bank debit/date, exact principal + interest sum, unconsumed transaction, evidence ownership, duplicate source rows and principal not exceeding borrowing. Existing statement replacement and bank matching see the consumed transaction. A correction cannot bypass a closed payment period.

Targeted tests exercise payment/correction history, bank evidence, duplicate matching, date and tenant rejection, principal ceilings, statement replacement protection, no duplicate ledger posting, budget offsets, extra payments, unassigned payments and API access. Local browser checks cover financed/cash summaries, collapsed details, payment forms and no-evidence states.
