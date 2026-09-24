# Invoice-first repair review — 2026-09-24

The everyday workflow is `/repairs`: upload an invoice, inspect the existing repair card, and answer missing payment questions inline. `/finance/repairs` now directs users there; bill/payment/reserve forms remain available under **Advanced accounting tools** (`?advanced=1`).

| Before | After | Why |
| --- | --- | --- |
| Re-enter repair details into accounting commands | Prefilled existing repair with paid/partial/unpaid/unknown question | Owner handles repairs, while carrier deductions already belong to settlements |
| Every historical repair requires a separate accounting form | Select matching invoices and apply the same payment answers together | Avoid repetitive entry without guessing which repairs were cash or Zelle |
| Unknown balances and ledger mechanics dominate each card | Invoice differences and payment questions first | Separate operator questions from book reconciliation |
| Uploaded repair original lives only at a local/remote attachment path | Exact PDF also preserved with the repair in one database transaction | Keep stable evidence for subsequent review |

Confirmations preserve amount, optional payment date, method, funding source, note, repair snapshot and previous revision. Corrections append evidence. Changed repair details invalidate the old confirmation. The service enforces business access, decimal amounts, partial-payment bounds, duplicate requests and stale edits. Invoice conflicts and free-work/recovery cases cannot be batch-confirmed or marked paid without resolving the cost treatment.

A confirmation is owner-supplied evidence, not a posted accounting payment, proof of a cash count, or a reconciled statement. It does not change cash, expenses, reserve funding or owner reimbursement. The current cash/ledger reconciliation remains available in advanced tools. Unknown funding and dates remain unknown. Mixed payments can be identified with a note; allocating their individual funding portions still uses the accounting workflow.

Batch eligibility requires an extracted matching total, no linked obligation, no prior confirmation and no amount/date/cost-treatment exception. In the current local history, 28 of 58 repairs qualify; this is not a payment verification claim. No historical confirmation was saved by the agent.

New PDF uploads retain the existing parser and legacy repair/reserve/journal behavior, while atomically preserving the PDF evidence. This checkpoint does not add OCR for unreadable images, auto-detect paid stamps, or replace the legacy posting behavior. The full automated repair-to-new-ledger migration remains an explicit later checkpoint, not a completed cutover.

Validation: 63 targeted backend tests passed (confirmation, history, cashbook, finance and retention); frontend tests, scoped lint and build passed. Browser inspected desktop/mobile inline questions and batch controls without submitting invented payment facts. Repair calendar dates now render on their recorded day rather than shifting back a day in US timezones. Production unchanged.


## Current behavior — account and reimbursement integration, 2026-09-24

This supersedes the earlier evidence-only checkpoint above. New single-repair forms default to paid in full and the invoice date; saved answers remain intact. Choosing an account sets its personal/business ownership. Personal payments also ask whether the full amount paid remains owed.

When that answer is yes and the dated amounts pass checks, saving records an accrual repair bill on the invoice date and an owner-funded vendor payment on the payment date. It creates one repair expense and one owner claim. Partial payments leave the remainder with the vendor. Bank Monitor's Owner reimbursements section can process eligible historical confirmations or confirm selected personal payments remain owed, then match existing business bank/cash payments to reduce the claim. It never sends money.

Unknown/already-reimbursed payments, missing dates, stale facts, existing manual obligations and closed periods stay in review. Note-only amendments preserve postings; financial changes require an explicit accounting correction. Legacy report entries are not added to the new ledger totals.

Payment accounts now have primary Add/Save and secondary Cancel actions, account-type choices, consistent focus/disabled states and an explicit Balance & connection view. Links use existing accounting statements or authorized Bank Monitor sources, not guessed suffix matches. Observed personal card balances do not become business debt, and observations do not establish reconciled cash.
