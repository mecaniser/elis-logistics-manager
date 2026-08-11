# Financial Reporting Architecture v1

Status: Proposed
Owner: Architecture & API Contracts
Audience: Product, backend, frontend, QA, data migration
Last updated: 2026-08-11

This document maps the reporting domain that exists today and defines the target v1 boundaries. It is an architecture contract, not a claim that the target is implemented.

## Current domain map

### Sources of financial facts

| Current source | Financial meaning | Current posting/report behavior |
|---|---|---|
| `Settlement` | Weekly revenue, deductions, reimbursements, cash adjustments, trailer allocations, and repair reserves | Creates one journal entry. Shared-account tenants post positive `net_profit` as cash and settlement income. Per-asset tenants post gross revenue, categorized expenses, and reimbursements through receivables. Zero or negative shared-account net profit produces no entry. |
| `Repair` | Vehicle repair cost and whether reserve funds paid it | Creates a maintenance-expense/cash journal entry when cost is positive. Reserve withdrawals use a separate ledger. |
| `RepairReserveLedger` | Earmarked operational reserve deposits, withdrawals, and adjustments | Used by reserve APIs. It is not part of the general ledger or current financial statements. |
| `Truck` | Vehicle acquisition, loan, depreciation, and resale assumptions | Balance sheet reads `total_cost` and `current_loan_balance` directly. Loan payoff is replayed from settlement and repair history. Depreciation may be calculated directly if no depreciation ledger balance exists. |
| `ChartOfAccount` | Tenant and optional vehicle-scoped account definition | Account codes and account scope vary between shared-account and LS Logistics per-asset modes. |
| `JournalEntry` and `JournalEntryLine` | Double-entry accounting record | P&L and cash/account balances read posted lines. Entries are replaced on source updates. No durable posting revision or report snapshot exists. |

### Current report read paths

```text
Settlement / Repair writes
        |
        +--> JournalEntry + JournalEntryLine --> Income statement
        |                                  \--> General ledger / trial balance
        |
        +--> operational tables ------------------------------+
        |                                                     |
Truck acquisition / loan / depreciation fields --------------+--> Balance sheet
        |
Settlement + Repair replay --> derived current loan balance --+
```

The current income statement is ledger-derived. The current balance sheet is hybrid: cash and receivables come from the ledger, fixed assets and loan balances may come from `Truck`, and retained earnings is recalculated from settlements and repairs. A report can therefore be internally inconsistent even if every journal entry balances.

### Current API surface

All paths are under `/api/accounting`.

| Method and path | Scope | Response model | Material contract issue |
|---|---|---|---|
| `POST /chart-of-accounts/initialize` | Tenant | `ChartOfAccount[]` | Logistics-only, mutates accounts, 409 if initialized. |
| `DELETE /chart-of-accounts/reset` | Tenant | Message object | Destructive and immediate; frontend sends a confirmation parameter that backend ignores. |
| `GET /chart-of-accounts` | Tenant | `ChartOfAccount[]` | Optional type, active, and truck filters. |
| `POST /chart-of-accounts` | Tenant | `ChartOfAccount` | Duplicate code is a free-text 400. |
| `GET /chart-of-accounts/{account_id}` | Global ID | `ChartOfAccount` | Does not require or filter by tenant. |
| `GET /journal-entries` | Tenant | `JournalEntry[]` | No pagination or posting status/version. |
| `POST /journal-entries` | Tenant | `JournalEntry` | Float money, free-text 400 errors, no idempotency key. |
| `GET /journal-entries/{entry_id}` | Global ID | `JournalEntry` | Does not require or filter by tenant. |
| `GET /general-ledger` | Account ID | `GeneralLedger` | Does not require tenant; account lookup and lines are not tenant-filtered. |
| `GET /balance-sheet` | Tenant, as-of date | `BalanceSheet` | Hybrid sources, no basis or policy version, may mutate chart of accounts while reading. |
| `GET /income-statement` | Tenant, period, optional truck | `IncomeStatement` | Ledger-derived; LS Logistics requires truck. No basis or policy version. |
| `GET /export/journal-entries` | Tenant | File | Direct export with no run, snapshot, or reconciliation gate. |
| `GET /export/general-ledger` | Tenant and account | File | Direct export with no run or reconciliation gate. |
| `GET /export/balance-sheet` | Tenant | File | Direct export of hybrid report. |
| `GET /export/income-statement` | Tenant | File | Direct export with no run or reconciliation gate. |
| `GET /export/trial-balance` | Tenant | File | Direct export; no persisted trial-balance result. |
| `GET /tax-year-summary` | Tenant, year | Unversioned object | Combines P&L and balance-sheet fields. |
| `GET /schedule-c` | Tenant, year | Unversioned object | Simplified hardcoded category mapping. |
| `POST /quick-entry/trailer-rental` | Tenant | `JournalEntry` | Uses query parameters for a mutation. |
| `POST /quick-entry/trailer-expense` | Tenant | `JournalEntry` | Uses query parameters for a mutation. |

The frontend also calls income/expense CSV import, depreciation calculate/record, and tax-package export routes that are not present in the backend. It sends `source` to income statement and `truck_id` to balance sheet even though the backend ignores them.

### Current invariants and gaps

Confirmed invariants:

- Settlement and repair route handlers own the transaction boundary for their operational row, related ledger rows, reserve rows, and trailer-split rows.
- Journal validation requires at least one line, one positive side per line, accounts from the entry tenant, and debits/credits within one cent.
- `tenant_id` is explicit on entry headers and lines.
- Loan payoff calculations replay settlement and repair history from original loan amount rather than trusting the stored current balance.

Gaps that block trustworthy financial-report exports:

- There is no reconciliation domain, posting-event ledger, accounting policy version, close state, report snapshot, or export gate.
- Money crosses the API as JSON numbers and is converted through floats in several report paths.
- A read can create missing chart-of-account rows.
- The model does not expose the `deleted_at` column added by an ad-hoc migration, and that migration is not registered in startup migrations.
- The posting uniqueness index identifies only tenant, reference type, and reference ID. It cannot preserve source revisions or multiple scheduled postings such as monthly depreciation.
- Current report schemas do not carry currency, basis, scope, source watermark, reconciliation outcome, or trace identifiers.
- Tenant authorization is a client-selectable header plus session authentication. Three accounting reads omit tenant enforcement entirely.
- QA confirmed exploitability rather than a documentation-only risk: no-header accounting disclosure and cross-tenant account, journal-entry, and general-ledger reads succeed on the current surface. This is a release blocker for every retained accounting/report/export route.

## Target v1 architecture

### Principles

1. The posted general ledger is the only financial-statement source of truth.
2. Operational records emit versioned posting events; they do not define report totals directly.
3. Every report is reproducible from a ledger high-watermark, policy version, scope, and request parameters.
4. Reconciliation is explicit and machine-readable. A balanced journal is necessary but not sufficient.
5. Export is a governed state transition, not a second report calculation.
6. Tenant and entity scope is enforced server-side at every boundary.
7. Money is decimal text with an ISO 4217 currency, never a binary float in a public contract.
8. There is one authoritative book ledger. Tax and lender outputs are explicit adjustment layers over a frozen book snapshot, never alternate ledgers that silently replace book facts.
9. Unknown policy or evidence is a contract state. The system blocks affected readiness and never guesses gross/net treatment, entity eligibility, reserve ownership, debt principal, or asset basis.

### Bounded contexts

| Context | Owns | Does not own |
|---|---|---|
| Operations | Settlements, repairs, reserve activity, vehicles, source documents | Journal-entry shape or financial-statement presentation |
| Posting | Immutable posting events, posting rules, posting attempts, journal revisions, idempotency | Report layout or operational edit workflows |
| Ledger | Accounts, journal entry revisions, lines, periods, ledger sequence | Operational source fields |
| Reconciliation | Expected-versus-posted checks, variances, exceptions, readiness status | Repairing source records automatically |
| Asset accounting | Asset register, cost-basis components, depreciation events, disposal | Vehicle operational performance |
| Debt accounting | Debt instruments, scheduled/actual principal and interest, balance roll-forward | Profit-allocation business forecasts |
| Reporting | Report definitions, report runs, snapshots, typed results | Mutating postings or operational records |
| Export | Eligibility decisions and immutable artifacts generated from completed report runs | Recomputing report totals |
| Policy and close | Effective-dated posting templates, book/tax/lender layers, unresolved decisions, period status, approvals | Editing historical policy versions after use |
| Evidence | Source files, hashes, provenance, verification state, and links to source/subledger facts | Treating an uploaded file as verified without reconciliation |

### Data flow

```text
Operational transaction
  -> source evidence + operational subledger record
  -> outbox posting event (same database transaction)
  -> effective-dated gross or net posting template selected by policy version
  -> immutable journal revision + monotonic ledger sequence
  -> source-to-ledger reconciliation
  -> report run captures sequence, policy, basis, currency, and scope
  -> typed report result
  -> export eligibility evaluation
  -> immutable export artifact
```

The outbox is a table written atomically with the operational change. A worker can retry delivery without losing the source write or double-posting it.

### Core target records

| Record | Required identity and version fields | Purpose |
|---|---|---|
| `posting_event` | `event_id`, tenant, source type/ID/version, event type/version, occurred date, payload hash | Immutable instruction to create, reverse, or replace a posting. |
| `posting_attempt` | event, attempt, rule version, status, error | Retry and operational visibility. |
| `journal_entry_revision` | stable entry ID, revision, status, event ID, policy version, ledger sequence | Append-only accounting effect. Replacement posts reversal plus new revision. |
| `accounting_policy` | `policy_version`, effective dates, supported bases, rule-set hashes | Locks mapping and recognition logic for a report. |
| `settlement_posting_template` | template ID/version, `gross_principal` or `net_agent`, effective range, approval state | Prevents tenant-name inference and makes revenue treatment explicit. |
| `policy_decision` | decision code, state, owner, evidence requirements, effective range | Preserves unresolved accounting questions as `approved`, `rejected`, `pending`, or `unknown`. |
| `source_evidence` | evidence ID/version, source hash, provenance, verification state, tenant/entity scope | Connects subledger facts and journal lines to immutable support. |
| `accounting_period` | entity, start/end, status, lock version, approvals | Enforces open/close/lock rules and prevents destructive historical edits. |
| `reconciliation_check` | check ID/version, scope, status, expected/actual, variance | Machine-readable evidence that posting and ledger invariants hold. |
| `report_run` | run ID, report type/schema version, request hash, source cutoff, ledger watermark, policy/layer versions, status | Reproducible report execution. |
| `report_result` | run ID, result checksum, typed payload | Immutable financial statement result. |
| `report_package` | package ID/version, run IDs, snapshot manifest, eligibility decision, checksum, lifecycle status | Immutable lender/management/tax-organizer package built only from frozen report snapshots. |

### Accounting basis and policy version

`accounting_basis` and `accounting_policy_version` are separate:

- `accounting_basis` describes recognition timing. The v1 enum is `accrual` or `cash`.
- `accounting_policy_version` identifies the complete rule set: account mappings, materiality, depreciation convention, retained-earnings treatment, cash-flow classification, and posting schemas.
- `report_schema_version` describes only the response shape.

The first production policy should support `accrual`. `cash` must remain unavailable until cash receipt/payment events and their reconciliation checks exist. The API returns `ACCOUNTING_BASIS_UNAVAILABLE` instead of silently approximating cash basis from settlement net profit.

Every run also declares `reporting_layer`:

- `book` reads the authoritative book ledger and book subledger controls.
- `tax` starts from the same frozen book snapshot and applies a versioned, accountant-approved book-to-tax adjustment set. Section 179, bonus depreciation, MACRS, limitations, and recapture never overwrite book postings.
- `lender` starts from the same frozen book snapshot and applies a versioned lender presentation/adjustment set plus the lender's request profile. It cannot claim CPA preparation, audit, review, or certification unless separately authorized outside this contract.

An unavailable layer returns a typed policy/readiness state. The service never falls back from tax or lender to book while retaining the requested label.

Policy versions are immutable after use. A correction creates a new version with an effective range. Re-running an old report defaults to its original policy version; opting into a newer version creates a distinct run.

Settlement posting uses an effective-dated `gross_principal` or `net_agent` template approved for the legal entity and revenue stream. A missing, overlapping, expired, or unapproved template produces `unknown` readiness and blocks posting/report packages for the affected scope. Tenant display name and per-asset mode are never template selectors.

### Ledger rules

- Each committed posting receives a tenant-scoped, monotonically increasing `ledger_sequence`.
- A report reads entries with `ledger_sequence <= ledger_watermark` and `effective_date` inside its scope.
- Posted entries are never edited or deleted. Corrections reverse the prior revision and post a replacement.
- Each line has `amount_minor` or canonical decimal text, currency, account, debit/credit direction, and optional asset/debt dimensions.
- Entry totals must balance exactly at currency precision. The current one-cent tolerance is not part of v1.
- Source identity is `(tenant_id, source_type, source_id, source_version, event_type, event_version)`. An idempotency key maps to exactly one accepted event and request hash.

### Reconciliation model

Reconciliation answers whether the source population, posting population, and ledger agree for a report scope.

Required checks:

- Source completeness: every in-scope postable source version has a terminal posting result.
- Posting uniqueness: no source version/event type has more than one active accounting effect.
- Posting currency and balance: entries balance exactly and use supported currency.
- Source-to-ledger amount agreement: expected dimensions and totals match posted lines.
- Orphan detection: every source-linked entry resolves to a source record and event.
- Asset roll-forward: opening cost and accumulated depreciation plus additions, disposals, and depreciation equal closing balances.
- Debt roll-forward: opening principal plus draws minus principal payments and adjustments equals closing principal.
- Trial balance: aggregate debits equal credits at the report watermark.
- Statement equations: assets equal liabilities plus equity; cash-flow opening plus net change equals closing cash.
- Suspense: opening-balance and classification suspense accounts are zero for final statements and every package.
- Evidence: material balances and required source/subledger facts meet the evidence policy for the requested layer.
- Policy: entity, gross/net template, reserve treatment, debt source, asset basis, and layer eligibility decisions are resolved for the scope.
- Period: the requested cutoff obeys period locks, late-event policy, and required close approvals.

The frontend-facing readiness state is exactly `pass`, `block`, or `unknown`:

- `pass`: every required check and policy decision has a terminal passing result at the frozen source cutoff.
- `block`: a known failed check, missing required evidence, nonzero suspense balance, prohibited period state, or ineligible entity/layer prevents publication.
- `unknown`: the system cannot determine readiness because a policy decision is unresolved, the effective template is ambiguous, source coverage is not established, or a dependency could not be evaluated.

Both `block` and `unknown` fail closed for packages and exports. `unknown` must never render as a neutral, empty, or successful UI state. Warning-level nonblocking findings appear separately and do not replace the tri-state result.

### Report execution and snapshots

Report requests are asynchronous resources even if execution completes quickly. The service:

1. Validates tenant access, report parameters, policy/basis support, and period state.
2. Captures an immutable source cutoff: recorded-at timestamp, posting-event watermark, ledger watermark, source-version manifest/checksum, policy versions, period-lock version, and evidence-policy version.
3. Runs reconciliation against the same watermark.
4. Produces exactly one schema-versioned result or a typed failure.
5. Evaluates export eligibility from persisted reconciliation evidence.

Report results never mix operational-table values with ledger values. Debt and asset schedules may show operational identifiers as dimensions, but all financial totals come from ledger postings and schedule subledgers reconciled to ledger control accounts.

Every statement amount supports a tenant-scoped drilldown from report line to journal lines, posting event, operational subledger record, and evidence metadata. A drilldown lookup resolves `(server_selected_tenant_id, run_id, line_code, resource_id)` together; the tenant component never comes from a drilldown parameter. Cross-tenant or out-of-snapshot resources return 404 and are never disclosed through counts, labels, or timing differences.

Report packages are immutable manifests of completed report snapshots. The package renderer reads stored result payloads by checksum; it cannot invoke report calculations or advance a source cutoff. If fresher data is needed, the user creates new runs and a new package version.

### Period locks and suspense

Period status is `open`, `soft_closed`, `locked`, or `reopened`. Posting into a locked period is rejected. A correction requires an approved adjusting/reversing event in an open period; reopening creates a new lock version with actor, reason, and approval trail. Destructive chart resets and source re-imports are never permitted against a period that has produced a locked package.

Suspense is visible in reconciliation and drilldown. A balance may be used in a draft internal run, but any nonzero required suspense account forces `block` for final statements, tax layers, lender layers, and report packages. Each suspense item carries an owner, reason code, evidence request, due date, and resolution event.

### Security and tenancy

- Tenant authority is a mandatory request invariant for every accounting, policy, period, posting/source, evidence, reconciliation, report, drilldown, eligibility, package, artifact, export, download, and retained legacy-adapter contract. There are no read-only, aggregate, cached, file, or service-to-service exceptions.
- Authentication establishes a server-derived user or service principal. The authorization authority derives that principal's tenant allowlist and action permissions. Client data cannot supply either.
- `X-Tenant-ID` is required exactly once and selects one tenant from the server-derived allowlist; it is never authorization by itself. Missing, malformed, non-positive, duplicated/conflicting, or body/query/path-conflicting selectors return 400 before any repository query, existence check, aggregate, cache lookup, report resolution, or file lookup.
- A selected tenant outside the allowlist and an unknown tenant both return the same 404. The system does not disclose whether a foreign tenant exists.
- Every repository query begins with selected-tenant scope. Object lookups use `(selected_tenant_id, object_id)`. Missing and cross-tenant objects return the identical generic 404, including accounts, journal entries/lines, source records, evidence, runs, drilldowns, packages, artifacts, and export files.
- 403 is used only when the principal is authorized for the selected tenant but lacks the requested action, such as posting, approving, reopening, packaging, or downloading. It is not an object-existence response.
- Tenant IDs in bodies, query strings, paths, source payloads, idempotency metadata, or cached state cannot widen scope. Request schemas reject attempted secondary tenant selectors; response records may echo the server-resolved tenant.
- Report, reconciliation, and export IDs are opaque UUIDs and remain tenant-scoped.
- Export artifacts use short-lived authenticated downloads. Storage URLs are never returned directly.
- Logs may include tenant ID, run ID, check code, and trace ID, but not bank account numbers, report payloads, or source-document contents.

Authorization must run before validation or handler behavior that could disclose tenant state. Error shapes, status, timing, cache behavior, row counts, and content length should be equivalent for missing versus cross-tenant objects where practical. The target contract examples and exact 400/403/404 semantics are in [API and schema contracts](./api-contracts-v1.md#mandatory-tenant-authority-invariant).

### Destructive reset prohibition

The target has no chart-of-accounts or journal reset capability. Once financial records exist, corrections use versioned mappings, reversing entries, adjusting entries, and approved period workflows. The retained `DELETE /api/accounting/chart-of-accounts/reset` route is unavailable and returns `410 ACCOUNT_RESET_UNAVAILABLE` without querying or changing accounting data after tenant authority is established. Locked-period history, source evidence, snapshots, and packages are never reset or reinitialized destructively.

## Migration shape

1. Enforce the mandatory tenant-authority invariant on every retained accounting/report/export route; make destructive reset unavailable; prove no-header and cross-tenant denials before exposing any target endpoint.
2. Add versioned posting-event, journal-revision, reconciliation, report-run, and export tables without changing current financial results.
3. Emit posting events alongside current side effects and compare shadow postings without publishing them.
4. Backfill events and subledger records with deterministic source versions; produce a reconciliation baseline.
5. Turn on v1 report runs for internal comparison. Require zero unexplained error-level variances before user-visible use.
6. Move frontend reads to `/api/v1`, then enable export gates.
7. Freeze legacy financial exports, publish deprecation dates, and remove adapters only after usage and parity gates pass.

Schedule C remains a tax-organizer candidate, not a ready financial report. Its readiness is `block` until federal entity eligibility, tax year/method, line mappings, book-to-tax adjustments, and reviewer approval all pass; unresolved eligibility is `unknown`. No route, label, or package may imply Schedule C filing readiness from logistics business type alone.

No migration step may rewrite or delete production financial facts without a separately approved data-correction plan.

## Related

- [API and schema contracts](./api-contracts-v1.md)
- [ADRs, dependencies, and Product Lead handoff](./decisions-dependencies-handoff.md)
