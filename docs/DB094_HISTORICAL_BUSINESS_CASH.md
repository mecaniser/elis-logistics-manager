# Reviewed historical business-cash receipts

Historical vendor receipt and cashbook reconciliation are separate facts. This
manual workflow records a confirmed business cash handover against a current DBN
receipt without creating opening cash, cash counts, funding deposits, owner loans,
or synthetic statement transactions.

## Accounting and evidence

`POST /api/v1/accounting/dieselbridge/repairs/{id}/historical-business-cash-payments`
uses the authenticated accounting tenant and server-selected reviewer identity.
The strict body extends the existing verified-payment request with three required
true attestations: `business_cash_handover_confirmed`,
`actual_handover_date_confirmed`, and
`unreconciled_cash_coverage_acknowledged`. Source attempt ID/revision are required;
caller-provided transactions, receipt evidence, and personal funding are rejected.
The amount is the whole actual DBN cash receipt, not the quoted card-fee maximum.
The actual handover date comes from explicit owner confirmation when DBN itself
has no evidenced actual-payment date. Never infer that fact from a timestamp alone.

The service revalidates the live source invoice, settlement and receipt. It stores
immutable hashed evidence containing the source receipt, original date basis,
reviewer, server review timestamp, actual handover date and owner confirmation
note. Cash funding origin remains `not_established`; the confirmed business payer
is not converted into personal funding or an owner loan.

Canonical posting: debit the existing payable; credit cash for the evidenced
historical outflow. The existing payment projector creates the legacy journal and
one equipment reserve withdrawal on the handover date. Invoice expense is not
posted again. The enclosing route owns the transaction; an error rolls back all
proof, payment, journal, operation and reserve changes. Existing tenant locks,
closed-period guards, source-revision checks, source-attempt uniqueness,
idempotency, and compensating payment reversal continue to apply.

This is a ledger cash movement with unresolved balance coverage, not a statement
that physical cash started at zero or became negative. Available business cash
and reported opening/closing cash balances remain null while these active receipts
are unresolved. Raw ledger movement balances remain available with an explicit
`unreconciled_ledger` basis. Money and repair views display the coverage exception.
This exception cannot certify account coverage or fund additional reserves.

Both `ELIS_DIESELBRIDGE_FINANCIAL_ENABLED` and the separate default-off
`ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED` must be explicitly authorized and enabled
for execution. This change does not enable either flag, alter the worker, or
activate future automatic payments. No database migration or DBN API change is
needed. Normal business-cash payments still require a reconciled cashbook.

## Reconciliation later

The current follow-up is an audited reversal of the attested payment, followed by
recording the same source receipt against its verified cashbook transaction in one
reviewed transaction. Never add a second payment on top. The reserve net effect
must remain exactly one withdrawal and original evidence must remain preserved.
The historical coverage warning remains until active attestations are corrected;
adding an unrelated bank statement cannot silently clear it.

## Prepared owner batch, not execution authorization

All 15 source receipts total $19,262.85:

| Actual handover date, America/New_York | Count | Cash received |
|---|---:|---:|
| September 12, 2026 | 8 | $11,466.09 |
| October 21, 2026 | 2 | $2,744.67 |
| October 29, 2026 | 5 | $5,052.09 |

The owner confirmed all three date groups were actual business-cash handovers.
Before any production write, refresh all 15 source revisions, accepted repair and
payment states, period locks, equipment mappings and reserve balances. Verify the
batch identity and exact totals, then execute under one transaction with stable
per-receipt idempotency keys and post-commit reconciliation. Do not archive or
replace temporary 609 records in this payment operation. Publishing/deployment,
enablement/execution and any temporary-record replacement require their respective
explicit authorization.
