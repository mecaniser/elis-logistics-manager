# Reconciled finance implementation and rollout

## Status

Local implementation on `codex/reconciled-logistics-rebuild`. The new workspace is `/finance`. Production has not been deployed, historical business data has not been posted, and the actual business has not been switched to the new home page.

The application now supports source-preserving imports, reconciled CSV statements, matched deposits and bill payments, partial/split payments, credits/refunds, protected reserves, equipment recovery plans, assignment history, traced HELOC schedules, immutable balanced postings, reversals, closed periods, frozen reports, source-backed accountant packages and a separate five-section dashboard. Existing source records and legacy reports remain available. Legacy profit-derived payoff labels now explicitly identify forecasts.

## Configuration

- Existing session authentication remains in use. Set `APP_AUTH_TENANT_IDS` to the server-authorized comma-separated business IDs for that session principal. The client header only selects an allowed business. Missing authorization fails closed for new and retained accounting routes.
- Local development only: `ELIS_FINANCE_LOCAL_TENANTS=1` enables finance access when authentication is unconfigured **and** the request originates from loopback. Never use this as production configuration.
- Set `MOTIVE_API_KEY_TENANT_<business_id>` in the server environment. The app never accepts or displays the key. The connector uses GET vehicle history only, with a maximum 90-day window and preserved raw response. Provider access, mapping, pagination and odometer coverage require live verification before accepting distance.
- Existing SQLAlchemy startup creates the additive `finance_*` tables. PostgreSQL and SQLite DDL install immutable-history triggers. No existing settlement or repair table is rewritten.

## Setup and migration sequence

1. Confirm the metric dictionary and financial examples in `metric-dictionary.md`.
2. Configure tenant authority. Open Accounting and attach prior books, Schedule C/depreciation records and the approved treatment of owner funding, carrier revenue, book depreciation and tax basis. Confirm only supported policy items.
3. Add all business bank/card accounts in Money. Save each CSV mapping; use stable bank transaction IDs. Outflows and card charges are negative. Upload original CSVs and reconcile opening plus transactions to closing. Card balances owed are negative.
4. Enter opening journals and outstanding bills/owner claims from evidence. Equity-funded acquisitions and reimbursable owner advances are distinct: use supported journal treatment for equity; do not automatically turn all historical asset investment into reimbursement claims.
5. Confirm existing funded reserves and dated asset recovery plans. Targets are not funded balances. Use the correct truck earning pair and actual repair asset.
6. In the legacy comparison, recover original PDFs for each period. Retrieval preserves originals for review and reports unavailable sources as gaps. Extracted 77 Cargo load and fuel rows can prefill settlement review. Confirm vehicle, products, category mappings, accounting date and payout reconciliation before posting. Other layouts remain reviewable original documents with manual normalized entry.
7. Reconcile bills and settlement deposits. Approved CSV mappings can auto-match **unique exact references and exact amounts** to already recognized obligations/receivables. Ambiguous references, partial matches, changed documents and closed periods remain for review. No broad fuzzy matching is used.
8. Trace mixed-use HELOC activity by draw/use, rate, interest, principal and payer. Link the existing business claim and actual business payments. Supporting financing entries never create a second expense or reimbursement claim. Personal portions remain outside the ledger. Interest accrual is recorded as a supported bill/journal under the approved policy.
9. Connect Motive or upload exported/odometer evidence. Accept non-overlapping independent intervals. Measured MPG requires supported consumed gallons; purchase-based MPG requires a complete 28-day independent interval and identified diesel. GPS movement alone cannot create an unpaid-load allegation.
10. Compare source totals, ledger, cash, reserves, asset schedules and historical differences. Download draft packages while evidence remains incomplete. The accountant-ready package is blocked until policy, history, statements, matches, ledger balances and obligation schedules pass. The ZIP includes frozen reports, ledger CSVs, source-event history, evidence manifest and preserved originals.
11. Complete desktop/mobile acceptance with actual business records. Choose **Make reconciled finance the home page** in Accounting. Cutover requires a current passing snapshot and explicit recorded browser acceptance. Legacy reports stay at `/legacy-dashboard`.

## Operational boundaries and current limits

- Report figures follow the effective accounting date supplied during reviewed posting. Settlement load/service dates are preserved separately; cross-period accrual adjustments require supported accounting entries. No silent 28th-of-month shifting or weekly allocation estimates are applied.
- Equipment disposals require acquisition cost and accumulated depreciation to agree with the asset ledger. Card repayments require a complete operating/investing/financing allocation; the application does not assume all card spending was operating expense.
- Bank/card CSVs are reconciled statement imports, not a live bank-feed connection. Source transaction IDs must be stable. Unsupported statement formats require a mapping or normalized export.
- Motive response fields and coverage depend on the provider account. Raw fetch is implemented; complete consumption coverage is never inferred from tank-level snapshots.
- Owner financing allocations are evidenced entries, not an automatic tax-interest allocation algorithm. Prior filing basis and mixed-use allocation remain accountant-confirmed policy.
- No automatic money transfers, lender payments, tax preparation or filing.
- Immutable revisions are supported through reversals and replacement source references. Reverse dependent matches/payments before correcting their source obligation. Disposal corrections currently require operational review; they are not silently reversed.
- Verification has used SQLite, a disposable PostgreSQL 16 database and a synthetic local browser business. PostgreSQL additive DDL, exact decimal posting and all ten SQL immutability guards passed. A production-shaped staging migration and real-data parallel run remain release gates.

## Verification

See `verification.md` for exact test and browser outcomes. Existing unrelated backend failures and frontend lint debt are reported separately from the new module checks. No production verification is claimed.
