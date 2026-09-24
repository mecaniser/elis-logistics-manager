# Cashbook-backed repair payments

The application records payments; it does not move money.

1. Preserve the repair invoice and identify the incurred date, actual charge and asset. Review free work, recoveries, settlement deductions and amount discrepancies first. In Record a bill, select the existing repair to prevent creating a second obligation for that repair.
2. For a personal payment, select owner with supporting payment evidence. This substitutes an owner reimbursement claim for the vendor amount; it does not recognize the expense again. Do not use business cash for money that belonged personally to the owner.
3. For business cash, create a cash account nickname. Preserve a CSV cashbook with stable receipt/entry references and a separate closing-count document. Map its date, signed amount, description and ID columns. Reconcile opening cash plus all entries to counted closing cash. Order same-day entries in actual funding/spending order. The supporting count must state the date and amount; uploading an unrelated document does not establish those facts.
4. Match the existing bill to the cashbook outflow with payer cash. Partial payments and multiple bills sharing one transaction use allocated amounts. For Zelle, use the reconciled checking transaction with payer business. For a card purchase, use payer card.
5. Match cash withdrawals/deposits as transfers between bank and cashbook entries. They are not repair expenses. Match an owner contribution separately when it actually funded business cash.
6. Reimburse an owner against the replacement owner claim, not by creating another repair expense. Repair-reserve coverage applies only to the linked earning pair and funded reserve.

Opening cash counts support the cash schedule; confirmed opening ledger balances still need their supporting journal. Incomplete cash/account/obligation coverage keeps available cash provisional. This implementation does not fill historical cash counts, cash ownership or missing dates from an invoice alone.

API additions: Account.account_type accepts cash; Statement.cash_count_evidence_id is required for cash accounts; Payment.payer accepts cash. Statement count evidence remains in the immutable event and report evidence manifest. Workspace includes tenant-scoped legacy repair choices. Existing routes retain server-derived business authorization. No new database table or destructive migration is required.

| Before | After | Why |
| --- | --- | --- |
| Business payments required bank/card records | Counted cashbook entries can fund payments | Reflects cash-on-hand without assuming a bank transaction |
| Payment fields always labeled optional | Transaction or personal-payment evidence required by payer | Prevents misleading incomplete input |
| Recovered document options displayed hash filenames | Repair date and description identify the source | Makes the payment review usable without technical identifiers |

Verification uses isolated synthetic transactions; actual review data was not posted. The basic forms are available, while a guided per-repair intake remains a usability improvement rather than a claim of completed historical reconciliation.
