# Financial Reporting Rebuild: QA Matrix and Baseline Gate

Date: 2026-08-11  
Role: QA Gatekeeper  
Commit audited: `138788cdc8916f7a65153f021ff135b9536d4555` (`main`, detached worktree)  
Scope: ledger postings, reconciliation, financial statements, exports, tenant boundaries, migrations, backfill, rollback, and browser flows  
Production mutations: none

## Release decision

**NO-GO. Zero of nine hard gates currently has sufficient passing evidence.**

The current application can generate accounting screens and export files, but it cannot yet be treated as a trustworthy financial reporting system. The baseline reproduces cross-tenant disclosure, an unbalanced balance sheet, a broken retained-earnings roll-forward, future assets included before purchase, one-day browser date shifts, and incomplete rollback behavior.

## Hard GO/NO-GO rules

All gates are mandatory. The release is GO only when every gate is GO, the full automated suite is green, there are no unresolved Critical or High financial findings, and the evidence bundle is repeatable from a clean database.

| Gate | Hard GO condition | Required evidence | Baseline status |
|---|---|---|---|
| G1. Ledger postings and source reconciliation | Every supported source event produces exactly one balanced posting; edits replace or reverse the prior posting; deletes reverse/remove it; mappings, signs, dates, references, and transaction atomicity are exact. Aggregate source amounts reconcile to ledger control accounts to the cent. | Golden source fixtures for settlements, repairs, reimbursements, deductions, cash adjustments, trailer splits, debt principal/interest, depreciation, and manual entries; source-to-ledger row-level trace; duplicate/update/delete/rollback tests. | **NO-GO** |
| G2. Balance-sheet equality | For every tenant and as-of date, `Assets = Liabilities + Equity` within $0.01. No balancing plug is permitted. Negative and contra-account presentation must be explicit. | Seeded opening balance, financed asset, profitable/loss periods, depreciation, debt payoff, repair, and empty-ledger fixtures; API, UI, PDF, and Excel parity assertions. | **NO-GO: reproduced $40,500 imbalance** |
| G3. Retained-earnings roll-forward | `Ending RE = Beginning RE + net income - distributions + prior-period adjustments` within $0.01. Manual, automated, depreciation, and closing entries flow through one authoritative ledger model. | At least two fiscal years, year close/reopen, loss year, manual adjustment, depreciation, and owner distribution fixtures; income statement to equity roll-forward reconciliation. | **NO-GO: reproduced $500 discrepancy** |
| G4. Period cutoff and dates | A record belongs to exactly the intended accounting period in API, UI, exports, and ledger. Future acquisitions and liabilities are excluded before recognition. Timezone changes cannot move a financial date. | Boundary fixtures at month/quarter/year end, leap day, DST transitions, UTC/local browser rendering, late-arriving and backdated entries; inclusive start/end assertions. | **NO-GO: future asset included; UI dates render one day early** |
| G5. Debt and depreciation | Principal changes liability only; interest changes expense; payoff never drives debt below zero; as-of debt is replayable. Depreciation basis, method, convention, accumulated depreciation, and expense postings agree and never exceed basis. | Amortization schedules with rounding/final payment; early payoff; rate/term changes; MACRS and straight-line golden schedules; Section 179/bonus limits; disposal; journal/report reconciliation. | **NO-GO** |
| G6. PDF and Excel exports | Export values, labels, filters, dates, tenant, and totals exactly match the API/UI fixture. PDFs are readable with no clipping; Excel money cells are numeric with currency formats and totals are machine-verifiable. No cross-tenant content appears. | Byte-level file signatures, PDF text/table extraction, workbook cell-type/number-format/formula assertions, multi-page/large-ledger fixtures, empty and negative values, filename/content-disposition checks, browser download flow. | **NO-GO: files generate, but export incorrect statements; financial-statement XLSX amounts are strings** |
| G7. Tenant boundaries | Every accounting read/write/export requires authenticated tenant context and filters every parent and child object by that tenant. Cross-tenant IDs return 404/403 and reveal no names, balances, entries, or existence signal. | Two-tenant adversarial matrix across list/detail/general-ledger/report/export/manual-entry/account/truck filters; missing/invalid tenant tests; DB-level tenant consistency constraints. | **NO-GO: Critical disclosure reproduced** |
| G8. Idempotent backfill | Dry-run is read-only; first run yields expected inserts/updates; second and later runs yield zero changes and identical hashes. Crash/restart resumes safely without duplicates or partial reconciliation. | Production-shaped anonymized copy; before/after counts and control totals; duplicate source rows; forced crash at each chunk boundary; rerun and checksum evidence. | **NO-GO: no financial ledger backfill exists or is rehearsed** |
| G9. Migration and rollback | Forward migration is repeatable on SQLite and production-like PostgreSQL, preserves counts/control totals, and stays within lock/time budgets. Forced failure leaves no partial schema/data. A rehearsed rollback or verified backup restore returns both schema and financial totals to baseline. | Clean upgrade, upgrade from current production schema, double-run, injected failure, concurrent-read rehearsal, backup/restore timing, post-rollback smoke and reconciliation. | **NO-GO** |

## Current automated-test evidence

Command executed against an isolated temporary SQLite database and a temporary virtual environment:

```text
DATABASE_URL=sqlite:////tmp/<isolated>.sqlite PYTHONPATH=backend python -m pytest backend/tests -q
54 passed, 12 failed, 16 warnings in 2.12s
```

Test inventory:

| File | Tests | Relevant coverage observed |
|---|---:|---|
| `test_77_cargo_parser.py` | 13 | Parser fixtures, upload paths, toll mapping to a journal account, dashboard/analytics values. No full source-to-ledger reconciliation. |
| `test_estimated_settlement_miles_backfill.py` | 2 | Idempotent mileage estimation backfill only. |
| `test_repair_reserves.py` | 13 | Reserve cutoff, lifecycle sync, tenant isolation for reserve endpoints, idempotent reserve backfill, atomic settlement/repair rollback. Useful adjacent evidence, not a financial-reporting gate suite. |
| `test_repairs.py` | 6 | All six fail because tenant headers are absent or legacy status expectations remain. |
| `test_settlements.py` | 5 | All five fail because tenant headers are absent or legacy status expectations remain. |
| `test_trucks.py` | 25 | Loan replay, payoff forecasts, trailer split interest, reserve defaults, and lifecycle behavior. One current failure: financed trailer break-even sale price expected `$0`, received `$645`. No depreciation journal/report tests. |
| `test_vehicle_documents.py` | 2 | Not financial reporting. |

There is no dedicated accounting/reporting test module, no frontend unit/integration test command, and no CI workflow in the repository. Frontend production build passes. Frontend lint fails with **227 problems: 197 errors and 30 warnings**, including errors and stale-hook warnings in the accounting pages.

## Reproduced release blockers

### FQA-001 — Critical — cross-tenant accounting disclosure

With tenant 1 selected, the following tenant-2 resources returned HTTP 200 and full financial content:

- `GET /api/accounting/chart-of-accounts/{tenant_2_account_id}`
- `GET /api/accounting/journal-entries/{tenant_2_entry_id}`
- `GET /api/accounting/general-ledger?account_id={tenant_2_account_id}`
- The general-ledger endpoint also returned tenant-2 data with no `X-Tenant-ID` header.

Browser-side fetch reproduced the disclosure of the tenant-2 account name, entry description, line description, and `$123.45` balance while tenant 1 was active. The corresponding general-ledger export endpoint is tenant-scoped and returned 404, proving inconsistent boundary enforcement rather than an intentionally global model.

Code evidence: the detail account, detail journal entry, and on-screen general-ledger routes query only by numeric ID and do not depend on `get_tenant_id` (`backend/app/routers/accounting.py:177-183`, `272-278`, `281-348`).

### FQA-002 — Critical — balance sheet does not balance and violates as-of cutoff

Fixture:

- Balanced manual ledger revenue: debit Cash `$500`, credit Revenue `$500`, dated 2025-12-31.
- Future truck: purchase date 2027-01-01, cost `$100,000`, current loan balance `$60,000`.
- Balance sheet requested as of 2026-12-31.

Observed:

```text
Total assets                  $100,500.00
Total liabilities & equity    $60,000.00
Out of balance                $40,500.00
```

The future truck and loan were included before purchase. The report silently presents the unequal totals despite UI copy stating that the equation must always balance.

Code evidence: logistics fixed assets and loans sum current truck records without applying `purchase_date <= as_of_date` (`backend/app/services/accounting_service.py:835-841`, `923-933`).

Screenshot: `.gstack/qa-reports/screenshots/balance-sheet-imbalance.png`.

### FQA-003 — High — retained earnings ignores authoritative ledger income

For the balanced `$500` manual revenue fixture:

- Income statement net income: `$500.00`.
- Balance-sheet retained earnings: `$0.00`.
- Roll-forward discrepancy: `-$500.00`.

The logistics balance sheet overrides the retained-earnings account with a separate calculation from settlement and repair source tables. That excludes manual journal income and depreciation expense and creates two competing books (`backend/app/services/accounting_service.py:966-981`).

### FQA-004 — High — financial dates render one calendar day early

Browser evidence in America/New_York:

- Balance-sheet input/API date `2026-08-11` displays as `8/10/2026`.
- Journal and general-ledger entry dated `2025-12-31` displays as `12/30/2025`.
- Income-statement inputs `2026-08-01` through `2026-08-31` display as `7/31/2026 - 8/30/2026`.

The frontend constructs `Date` from date-only strings and calls `toLocaleDateString`, causing UTC-midnight dates to shift in negative offsets (`BalanceSheet.tsx:174`, `GeneralLedger.tsx:67-69`, `JournalEntries.tsx:83-85`). This can misstate month-end and year-end cutoffs to users even when the API filters the intended dates.

Screenshots: `.gstack/qa-reports/screenshots/balance-sheet-imbalance.png`, `.gstack/qa-reports/screenshots/income-statement-rollforward.png`, `.gstack/qa-reports/screenshots/general-ledger.png`, `.gstack/qa-reports/screenshots/journal-entries.png`.

### FQA-005 — High — debt and depreciation do not reconcile through one ledger

- The balance sheet replaces the loans-payable ledger balance with current values from truck records when nonzero.
- Fixed assets are taken from truck `total_cost`, not the asset ledger.
- Accumulated depreciation may come from journal account balances or fall back to a calculated schedule.
- Shared-account initialization creates accumulated depreciation as code `1600`, while balance-sheet lookup uses `1501`; depreciation journal creation also uses `1501` with a per-truck account.
- No test exercises depreciation calculation through journal entry, income statement, retained earnings, and balance sheet together.
- The full suite currently has one failing financed-trailer loan assertion.

These paths can each be locally plausible while disagreeing at report level.

### FQA-006 — High — export generation works but cannot certify financial correctness

Positive evidence:

- Balance-sheet and income-statement PDFs returned 200, began with `%PDF-`, opened with `pdfplumber`, and yielded one readable page.
- Balance-sheet, income-statement, and trial-balance Excel files returned 200, began with the ZIP/XLSX signature, and opened with `openpyxl`.
- Browser export buttons completed without console errors.

Blocking evidence:

- PDF and Excel faithfully exported the incorrect `$100,500` versus `$60,000` balance sheet.
- Balance-sheet and income-statement Excel amounts are preformatted strings such as `"$100,500.00"`, not numeric cells with currency formats, so downstream formulas and reconciliation cannot rely on them.
- No automated export parity tests exist.

### FQA-007 — High — migration failure can leave partial schema and rollback is unrehearsed

Positive evidence: the two startup migrations applied twice on an isolated SQLite schema and produced one marker per migration with the expected columns.

Forced-failure evidence: a migration that created a table and then raised did not write its `schema_migrations` marker, but SQLite retained the created table. This demonstrates that the marker protocol alone does not guarantee atomic rollback across supported databases. No automated startup-migration tests exist, no production-like PostgreSQL rehearsal is recorded, and documented rollback for most migrations is manual backup restore rather than a tested procedure.

## Browser flow evidence

Target: a local FastAPI/Vite production build on `127.0.0.1:8765` backed by a temporary seeded SQLite file. No production or repository database was used.

Visited:

- Dashboard
- Accounting index
- Balance Sheet
- Income Statement
- General Ledger
- Journal Entries

All pages loaded without JavaScript console errors. PDF and Excel buttons executed without console errors. That is smoke evidence only; it does not override the reproduced accounting and isolation failures.

Screenshots are stored under `.gstack/qa-reports/screenshots/` in this QA worktree.

## Required regression fixture set

The rebuild should ship with a reusable two-tenant fixture containing:

1. Opening cash, owner equity, accounts payable, and a financed vehicle acquisition.
2. Source settlements for gross revenue, categorized expenses, reimbursements, deductions, cash adjustments, zero-net, negative-net, and trailer allocations.
3. Repairs paid from cash and reserve, including update/delete/rollback paths.
4. Debt schedule with origination, interest, principal, rounding, extra payment, and payoff.
5. MACRS and straight-line assets, Section 179, bonus depreciation, and disposal.
6. Manual journal income, expense, owner contribution, distribution, and prior-period adjustment.
7. Dates immediately before/on/after month, quarter, year, leap-day, and DST boundaries.
8. A second tenant using colliding account, journal, truck, settlement, and repair IDs where possible.
9. Expected source totals, journal lines, trial balance, income statement, retained-earnings roll-forward, balance sheet, PDF text, and Excel typed cells.

Every fixture must carry deterministic expected cents and a trace key from source row to posting to report line.

## Minimum release evidence bundle

- Green full backend suite and green frontend test/build/lint gates.
- A dedicated accounting regression suite covering G1-G9.
- Two-tenant negative authorization results for every accounting route and export.
- Source-to-ledger reconciliation report with zero unexplained difference.
- Trial balance debit/credit equality and balance-sheet equality for every seeded cutoff.
- Retained-earnings roll-forward across at least two fiscal years.
- PDF visual/text inspection and Excel type/formula inspection for each report.
- Clean and production-upgrade migration rehearsals on PostgreSQL plus SQLite compatibility evidence.
- Backfill first-run, second-run, forced-crash/resume, and checksum evidence.
- Timed backup restore or reversible rollback rehearsal with post-rollback reconciliation.
- Desktop and mobile browser flows with exact financial dates and successful downloads.

Until this bundle exists and every hard gate is GO, the financial-reporting rebuild remains **NO-GO**.
