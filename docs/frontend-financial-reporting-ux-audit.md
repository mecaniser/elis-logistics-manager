# Financial Reporting Frontend UX Audit and Architecture

Date: 2026-08-11  
Owner: Frontend UI/UX  
Status: First-deliverable audit; no production mutation, deployment, merge, or financial-data changes

## Executive decision

Rebuild `/accounting` as a reconciliation-first financial reporting workspace, not as another dashboard of report cards. A lender package is trustworthy only when the user can see the reporting entity and period, the source and freshness of every statement, unresolved exceptions, whether the books balance, and who reviewed the package.

The current application has useful accounting primitives—journal entries, a general ledger, chart of accounts, P&L, balance sheet, tax reports, Excel/PDF download, tenant context, and vehicle finance/depreciation fields—but it does not yet expose a report-readiness model. Cash flow, bank reconciliation, debt schedule, consolidated asset/depreciation schedule, period close, comparative statements, report provenance, and lender-package review are absent as first-class routes and API contracts.

Do not label the product or an export "lender ready" until the readiness gates in this document are backed by source-grounded API fields. Unknowns are shown as unknown; zero is never used as a substitute for missing financial data.

## Audit scope and method

This audit traces the authenticated React routes in `frontend/src/App.tsx`, accounting navigation and pages, the shared API client in `frontend/src/services/api.ts`, and the accounting router, schemas, services, depreciation service, and export utility in `backend/app`. It is a static worktree audit. No authenticated runtime or representative generated PDF was available in this task, so visual behavior and final PDF rendering remain unverified.

Current frontend baseline:

- React 18 + React Router 6 + Vite 5 + TypeScript + Tailwind.
- Global tenant/business context is carried through `TenantProvider`; accounting requests use the shared `/api` client.
- The top navigation exposes one Accounting destination; all accounting subnavigation currently lives on the `/accounting` card grid.
- Desktop is constrained to `max-w-7xl`; mobile uses the same pages with responsive stacks and, on some ledger pages, alternate card layouts.
- There is no repository `DESIGN.md`, shared report table primitive, shared period selector, report shell, print stylesheet, or automated frontend test suite.

## Current-state route, component, and API map

| Route | Current page/component | Current dependency | What exists | Lender-readiness gap |
|---|---|---|---|---|
| `/accounting` | `Accounting.tsx` | Static link definitions | Card grid to eight accounting/tax tools | No workflow, readiness status, period/entity context, or exception priority |
| `/accounting/income-statement` | `IncomeStatement.tsx` | `GET /accounting/income-statement`; export endpoint | Date range, preset ranges, revenue/expense totals, PDF/Excel | No prior-period/YTD comparison, accounting basis, source freshness, drilldown, report status, or export review |
| `/accounting/balance-sheet` | `BalanceSheet.tsx` | `GET /accounting/balance-sheet`; export endpoint | As-of date, assets/liabilities/equity, PDF/Excel | No explicit out-of-balance delta, comparative date, source provenance, classification detail, or readiness gate |
| `/accounting/general-ledger` | `GeneralLedger.tsx` | chart of accounts + `GET /accounting/general-ledger`; export | Account/date filters, opening/ending balance, entries, CSV/Excel | One-account-at-a-time investigation; no reconciliation status, exception linkage, pagination, or source-document trail |
| `/accounting/journal-entries` | `JournalEntries.tsx` | journal list + chart of accounts; CSV/Excel | Filters, mobile line cards, desktop line table | No review/approval state, void/reversal workflow, attachment/source confidence, close-period guard, or stable deep link |
| `/accounting/chart-of-accounts` | `ChartOfAccounts.tsx` | chart initialization/reset/list | Account browsing and initialization/reset | Destructive reset is adjacent to reporting; no lender classification mapping, normal-balance cues, or change history |
| `/accounting/tax-year-summary` | `TaxYearSummary.tsx` | `GET /accounting/tax-year-summary`; **income-statement export reused** | Annual tax summary UI | Download filename says tax summary but payload is an income-statement export; not a true tax-summary or lender export |
| `/accounting/schedule-c` | `ScheduleC.tsx` | `GET /accounting/schedule-c`; **income-statement export reused** | Simplified Schedule C mapping | Download filename says Schedule C but payload is an income-statement export; mapping is not a signed/filing-ready form |
| none | none | none | — | Cash flow statement missing |
| none | vehicle detail finance blocks | trucks/ROI endpoints | Per-vehicle loan balance, interest, payoff projection exist | No contractual payment schedule, lender, maturity, current/long-term split, totals, or reconciliation to loans payable |
| none | vehicle detail depreciation block | vehicle fields + depreciation calculate/record APIs | Per-vehicle tax depreciation inputs/calculation exist | No consolidated fixed-asset roll-forward, book-vs-tax basis, disposal/impairment, accumulated depreciation reconciliation, or report route |
| none | none | plan marks reconciliation/bank feeds incomplete | — | Bank/account reconciliation cockpit missing |
| none | none | none | — | Readiness checklist, signoff, package manifest, and lender package missing |

### Current report data lineage

```text
Settlements / repairs / manual entries / depreciation entries
                       |
                       v
              Journal entries + lines
                       |
          +------------+-------------+
          |                          |
          v                          v
  Income statement            General ledger
          |
          +------------------- tax summaries

Vehicle records ---------> vehicle cost and loan overrides ----+
Depreciation service ----> calculated depreciation fallback ----+--> Balance sheet
Settlements + repairs ----> derived retained earnings -----------+
Ledger accounts ---------> cash, AR, AP, equity -----------------+
```

This mixed lineage is the largest readiness risk. `generate_balance_sheet` takes some values from the ledger, fixed assets from vehicle `total_cost`, depreciation from the ledger or a service fallback, loans from the ledger but then overrides them with vehicle fields when available, and retained earnings from settlements/repairs for logistics tenants. The response does not include a balance delta or lineage metadata. The UI must not imply that this is reconciled until the backend exposes and verifies those facts.

### Current PDF/export audit

- The browser downloads blobs immediately; there is no preview, contents checklist, generated-at timestamp, report basis, preparation status, or failure recovery beyond `alert()`.
- The PDF utility creates a generic ReportLab letter-size table using Helvetica, fixed margins, one title, optional business name, repeated column headers, beige rows, and grid lines.
- It does not define page headers/footers, page numbers, confidentiality, entity metadata, accounting basis, preparation timestamp, approval/signature, notes, source references, tagged-PDF structure, bookmarks, or document language.
- Tables do not define explicit column widths or wrapping policy, so long labels and wide reports are a clipping/legibility risk.
- Current PDF output has not been rendered and visually inspected in this task; PDF accessibility and lender usability are therefore unverified.
- Tax Year Summary and Schedule C reuse the income-statement exporter. Those buttons must be relabeled or blocked until dedicated export contracts exist.

## Prioritized UX findings

### P0 — trust and correctness gates

1. **No reconciliation/readiness truth model.** A lender-facing package can be downloaded without knowing whether cash is reconciled, journal entries balance, the balance sheet balances, source periods are complete, or debt/assets tie out.
2. **Balance sheet provenance is mixed and hidden.** Derived and ledger values are presented as a single authoritative statement without disclosing overrides/fallbacks or an out-of-balance amount.
3. **Misnamed tax exports.** Tax Year Summary and Schedule C download income statement payloads under different filenames.
4. **Missing cash flow, debt schedule, and fixed-asset roll-forward.** The required package cannot be completed from current first-class reports.
5. **No accounting-period close or review state.** A previously downloaded package can silently change after new entries or source edits.

### P1 — workflow and comprehension

6. **Information architecture is a tool catalog.** Users must know accounting terminology and choose among eight equal-weight cards instead of following review → resolve → approve → export.
7. **No shared reporting context.** Entity, period/as-of date, basis, comparative period, and consolidation scope are not persistent across reports.
8. **No statement-to-ledger drilldown.** Reviewers cannot move from a report line to contributing accounts, journal entries, and source documents while retaining context.
9. **No missing-vs-zero distinction.** Current numeric response shapes cannot tell the UI whether zero is verified, calculated, unavailable, or not applicable.
10. **No consolidated schedules.** Loan and depreciation data is fragmented across vehicle forms/details and accounting entries.
11. **Errors are dead ends.** Pages render a message or browser alert without retry, partial-data disclosure, request identity, or a safe route to the underlying exception.

### P2 — responsive, accessible, and export quality

12. **Report primitives are duplicated.** Formatting, filters, loading/error/empty states, and download logic vary by page.
13. **Accessibility semantics are incomplete.** Data tables do not consistently expose explicit header scope/captions; icon SVGs and focus behavior are inconsistent; immediate reloads can erase the user's reading position.
14. **Mobile reports are not designed for financial comparison.** Stacking individual values loses row/column relationships; large tables need deliberate frozen labels, column selection, or a line-item detail mode.
15. **Download is not review.** There is no on-screen print preview, package manifest, export validation, or parity check between screen and file.

## Target information architecture

Keep all reporting under the existing `/accounting` authorization boundary, but replace the card grid with a persistent accounting workspace.

```text
/accounting                              Reconciliation cockpit (default)
  /reconciliation                       Account readiness and exceptions
  /reports
    /profit-and-loss                    P&L
    /balance-sheet                      Balance sheet
    /cash-flow                          Cash flow statement
  /schedules
    /debt                               Debt schedule
    /assets                             Fixed assets and depreciation
  /readiness                            Package readiness and signoff
  /packages/:packageId                  Frozen review/export manifest
  /ledger
    /general                            General ledger
    /journal                            Journal entries
    /chart-of-accounts                  Chart of accounts
  /tax
    /year-summary                       Tax year summary
    /schedule-c                         Schedule C mapping
```

Compatibility requirement: existing `/accounting/*` URLs remain valid through redirects or route aliases. Do not break bookmarks.

### Persistent workspace hierarchy

1. **First:** entity/business, period/as-of date, accounting basis, and current readiness state.
2. **Second:** unresolved blockers and the next defensible action.
3. **Third:** statements and schedules, with line-level drilldown and export only after scope is clear.

Desktop uses a compact left subnavigation plus a sticky reporting context bar. Mobile uses a top context summary and a single “Accounting sections” disclosure; it must not hide the active period or readiness state.

## Target route/component dependency map

```text
AccountingWorkspaceShell
├── AccountingSubnav
├── ReportingContextProvider
│   ├── EntityScopeControl
│   ├── PeriodControl
│   ├── BasisIndicator
│   └── DataFreshnessIndicator
├── ReconciliationCockpitPage
│   ├── ReadinessSummary
│   ├── AccountReconciliationTable
│   ├── ExceptionQueue
│   └── ClosePeriodPanel
├── FinancialStatementPage
│   ├── StatementHeader
│   ├── ComparativeColumnControl
│   ├── FinancialStatementTable
│   ├── LineItemDrilldownDrawer
│   └── ReportNotesPanel
├── DebtSchedulePage
│   ├── DebtSummary
│   ├── DebtInstrumentTable
│   └── MaturityTimeline
├── AssetSchedulePage
│   ├── AssetRollforwardSummary
│   ├── AssetScheduleTable
│   └── DepreciationBasisToggle
└── ReportReadinessPage
    ├── ReadinessChecklist
    ├── PackageManifest
    ├── ReviewerSignoff
    └── ExportReviewDialog
        ├── ScreenPreview
        ├── PackageWarnings
        └── DownloadActions
```

Shared primitives should own currency/sign formatting, negative-value presentation, missing-value states, loading/error/partial states, keyboard semantics, and print behavior. Pages should receive normalized report view models rather than interpreting loosely typed dictionaries independently.

## Proposed API dependency contracts

These are frontend requirements, not claims that the backend already provides them. Backend/Product must confirm semantics before implementation.

| Frontend need | Proposed read contract | Required response facts |
|---|---|---|
| Persistent report context | `GET /accounting/reporting/context` | entity ID/legal name, period options, accounting basis, timezone, currency, last closed period |
| Cockpit readiness | `GET /accounting/reconciliation/summary?period=…` | accounts in scope, statement/ledger balances, difference, source date, status, owner, unresolved count |
| Exceptions | `GET /accounting/reconciliation/exceptions?...` | stable exception ID, severity, amount, account, source, reason, suggested action, resolution state |
| P&L | `GET /accounting/reports/profit-and-loss?...` | normalized rows, hierarchy, current/prior/YTD columns, basis, provenance, generated-at, completeness flags |
| Balance sheet | `GET /accounting/reports/balance-sheet?...` | normalized rows, comparative date, assets, liabilities/equity, explicit balance delta, lineage and completeness |
| Cash flow | `GET /accounting/reports/cash-flow?...` | operating/investing/financing rows, beginning/ending cash, reconciliation to balance sheet cash |
| Debt schedule | `GET /accounting/schedules/debt?...` | instrument ID, lender, original/current balance, rate/type, payment, maturity, current/long-term split, principal/interest by period, source confidence |
| Asset schedule | `GET /accounting/schedules/assets?...` | asset ID, class, in-service/disposal dates, beginning basis, additions/disposals, book and tax depreciation, accumulated depreciation, ending NBV, source confidence |
| Readiness | `GET /accounting/reporting/readiness?...` | versioned gate IDs, pass/block/unknown, evidence, blocker owner, last checked, materiality/tolerance used |
| Frozen package | `POST /accounting/reporting/packages` then `GET /.../:id` | immutable scope/manifest, source snapshot/version, checksums, preparer/reviewer, generated-at, export links |
| Drilldown | stable links from every report row | contributing account IDs, journal entry IDs, source references, filters preserved in URL |

Contract rules:

- Every money field must distinguish `0`, `null`/unknown, and not-applicable.
- Every report returns `entity`, `period`, `basis`, `currency`, `generated_at`, `source_cutoff`, `status`, `warnings`, and a stable version/snapshot ID.
- Readiness statuses are `pass`, `block`, or `unknown`; unknown never collapses to pass.
- Client-side totals may be used for display cross-checks but never as the authoritative accounting calculation.
- Exports are generated from the same immutable report snapshot used for on-screen review.
- Tenant/entity authorization must be enforced server-side on every ID-based report, account, entry, package, and drilldown request.

## Phased implementation plan

### Phase 0 — business rules and data contracts (blocking; no UI claims)

Product/Accounting confirms the unknown inputs below. Backend publishes example schemas with `unknown` and partial-data cases, defines report snapshots and readiness gates, and resolves the current mixed-lineage balance-sheet contract. Add contract tests before the new frontend calls the APIs.

Exit: signed-off definitions for entity scope, basis, periods, reconciliation, report lines, debt, assets, readiness, and package contents.

### Phase 1 — safe frontend foundation

Implement route aliases, `AccountingWorkspaceShell`, persistent subnavigation/context bar, normalized currency/financial-value component, statement table primitive, accessible loading/empty/error/partial states, URL-backed filters, and print tokens. Keep current pages functional behind the new shell.

Exit: keyboard/mobile/desktop shell works with current endpoints; existing URLs and downloads still work; no financial calculations move to the client.

### Phase 2 — reconciliation cockpit and readiness truth

Implement cockpit summary, account reconciliation table, exception queue, source freshness, blocker ownership, and explicit unknown states. Do not add “ready” styling until all versioned gates pass. Link exceptions to the ledger/source trail.

Exit: a reviewer can identify every blocking/unknown item, open its evidence, and return without losing entity/period context.

### Phase 3 — lender statements

Rebuild P&L and balance sheet on normalized row contracts with prior-period/YTD comparisons, collapsible hierarchy, provenance, notes, and stable drilldown. Add cash flow with beginning-to-ending cash reconciliation. Preserve current routes through aliases.

Exit: each visible total matches the API snapshot and exported total; balance sheet and cash checks are explicit.

### Phase 4 — debt and asset/depreciation schedules

Add consolidated schedules with exception states for missing contractual terms, book-vs-tax separation, loan balance tie-out, fixed-asset roll-forward, and statement cross-links. Do not infer lender, payments, maturity, useful life, salvage value, or disposal data.

Exit: debt ties to balance-sheet debt; ending accumulated depreciation and net book value tie to balance sheet; missing inputs block readiness transparently.

### Phase 5 — package review, accessible PDF, and responsive hardening

Implement frozen package manifest, preparer/reviewer signoff, screen preview, export warnings, and dedicated statement/schedule PDFs from the same snapshot. Render and visually inspect representative short, long-label, multi-page, negative-value, zero, and partial-data PDFs. Complete keyboard, screen-reader, high-zoom, narrow-mobile, tablet, and desktop QA.

Exit: package identity and checksums are stable, screen/export parity passes, and no blocker/unknown package can be represented as ready.

### Phase 6 — regression and rollout gate

Add route/component tests, API contract tests, accessibility checks, visual regression at defined viewports, PDF extraction/render checks, and end-to-end review → resolve → signoff → export coverage using deterministic non-production fixtures.

Exit: Product & Delivery Lead receives evidence and decides integration/release. This frontend task does not merge or deploy.

## Acceptance criteria

### Global trust and context

- Every accounting screen identifies legal entity/business, period/as-of date, accounting basis, currency, source cutoff, and generated-at time.
- Filters are URL-backed and survive refresh, navigation, and drilldown/back.
- Zero, unknown, not applicable, and loading are visually and semantically distinct.
- A stale, partial, blocked, or unknown report cannot display a green/ready state.
- All totals and readiness decisions come from server contracts; the frontend does not invent missing financial values.

### Reconciliation cockpit

- Account rows show ledger balance, external/source balance when available, difference, source/freshness, status, unresolved count, and owner.
- The cockpit shows journal debit/credit balance, balance-sheet delta, cash-flow cash delta, debt tie-out, asset tie-out, and missing-source checks.
- Each blocker/unknown has a stable link to evidence and an explicit next action.
- Reopening a closed period or changing a reconciled source requires an auditable state change defined by Product/Accounting.

### P&L

- Current period, approved comparison period, and YTD are readable without horizontal ambiguity on desktop and through an intentional column/line-item mode on mobile.
- Revenue, expense, and net income totals match the snapshot API and PDF/Excel outputs to the approved rounding tolerance.
- Every material line drills to contributing accounts and entries with context preserved.
- Negative values use a redundant text/sign treatment, not color alone.

### Balance sheet

- The UI displays `Assets`, `Liabilities + Equity`, and the explicit difference.
- A non-zero or unknown difference blocks readiness.
- Current and comparative as-of dates are clearly labeled.
- Derived values, overrides, and fallbacks expose provenance and cannot masquerade as reconciled ledger balances.

### Cash flow

- Operating, investing, and financing sections are separately totaled.
- Beginning cash + net change = ending cash, and ending cash ties to the balance sheet for the same snapshot.
- Classification rules and non-cash adjustments are visible in notes/drilldown and confirmed by Accounting.

### Debt schedule

- Each obligation shows lender, asset/collateral link if applicable, original/current balance, rate and type, scheduled payment, maturity, current/long-term classification, and principal/interest detail—or explicitly marks the field unknown.
- Schedule totals tie to balance-sheet loans payable; differences block readiness.
- Forecast/projected payoff is clearly separated from contractual maturity and scheduled payments.

### Asset/depreciation schedule

- Each asset shows identity, class, placed-in-service date, beginning basis, additions/disposals, method/life, current depreciation, accumulated depreciation, and ending net book value—or marks missing inputs unknown.
- Book depreciation and tax depreciation/Section 179/bonus are not conflated.
- Ending gross assets, accumulated depreciation, and net assets tie to the balance sheet.

### Readiness and package review

- Readiness gates are versioned, evidence-backed, and display pass/block/unknown with last-check time.
- Package manifest lists every statement, schedule, note, period, entity, version, and warning before download.
- The package is created from a frozen snapshot; later source changes mark it superseded rather than silently changing it.
- Preparer/reviewer identity and timestamps follow the authority model Product approves.

### Accessibility and responsive behavior

- All workflows are keyboard operable with visible focus; focus moves to errors/dialog titles and returns to the trigger on close.
- Tables have captions and explicit header associations; status and negative/positive meaning do not rely on color alone.
- Live load/error/export messages are announced without disruptive browser alerts.
- Touch targets are at least 44×44 CSS pixels; no control depends on hover.
- At 320/375/768/1024/1440 CSS pixels and 200% zoom, core totals, labels, readiness state, and actions remain available without page-level horizontal scrolling.
- Mobile preserves financial comparison through deliberate column selection or line-item detail, not an ambiguous card dump.

### PDF and export

- Dedicated exports exist for each labeled report; no renamed payloads.
- Every PDF includes legal entity, report title, period/as-of date, basis, currency, generated-at time, snapshot/package ID, page X of Y, and confidential/draft/final state.
- Multi-page tables repeat headers, preserve line hierarchy, avoid clipped/widowed totals, and use legible minimum type sizes.
- PDFs expose document language, logical reading order, real text, meaningful table structure where the generator supports it, and bookmarks for package sections; remaining accessibility limitations are documented.
- Screen totals and PDF/Excel totals match the same snapshot and approved rounding policy.
- Final QA renders every representative PDF page to images and inspects first, last, page breaks, long labels, negatives, zero/unknown values, and totals; text extraction also verifies required metadata and values.

### Authorization and isolation dependency

- Every ID-based account, journal entry, ledger, report, package, and drilldown endpoint verifies the active tenant/entity server-side.
- Switching businesses invalidates cached report data and visibly resets report context.
- No report/export URL or browser cache reveals another tenant's metadata or values.

## Unknown business inputs — do not invent

### Blocking for Phase 0

1. Which legal entity/entities and whether consolidated or per-business reports are required?
2. Who is the target lender, and what exact statement periods, comparisons, schedules, notes, and certification language do they require?
3. Are statements cash basis, accrual basis, tax basis, or another basis? Is more than one basis required?
4. What are the authoritative opening balances and conversion date for the accounting ledger?
5. Which bank/credit accounts are in reconciliation scope, what is the source of statement balances, and what tolerance/materiality is allowed?
6. What makes a period complete/closed, who may close/reopen it, and what events invalidate prior readiness/signoff?
7. For each debt instrument: lender, origination date, original principal, current verified balance date, rate/type, payment frequency/amount, maturity, fees, balloon terms, collateral, and current/long-term classification rule.
8. Is the existing replay/projected vehicle payoff model operational planning only, or may any part support lender reporting?
9. For each asset: legal owner, class, placed-in-service date, original basis, additions, disposals, salvage value, book useful life/method, tax method, Section 179/bonus treatment, and impairment policy.
10. What is the authoritative rule for owner contributions/draws, retained earnings, repairs/reserves, trailer allocations, loan principal, and interest in the three statements?
11. What readiness gates, evidence, reviewer roles, signoff wording, and package retention/versioning policy are required?
12. What currency/rounding/negative-number convention and timezone/report cutoff apply?

### Needed before final PDF/package design

- Legal name, address, logo/brand usage, confidentiality wording, preparer/reviewer labels, and draft/final watermark rules.
- Package order, cover page, table of contents, notes/footnotes, page size, delivery channel, and whether digitally accessible/tagged PDF is a contractual requirement.
- Whether lender-facing schedules require monthly projections, historical actuals only, or both.
- Whether tax reports belong in the lender package or remain a separate workflow.

## Safe bounded frontend work available after contract approval

The first independently testable frontend slice should be Phase 1 only: workspace shell, route aliases, URL-backed report context, normalized financial value display, accessible state components, and a statement table driven by current report contracts. It should not change calculations, claim readiness, rename existing exports, or add placeholder financial values.

## Handoff to Product & Delivery Lead

Decision needed: approve the reconciliation-first information architecture and assign owners for the 12 Phase 0 business inputs. Backend/accounting work is a prerequisite for truthful readiness, cash flow, debt, asset roll-forward, and frozen package contracts. Frontend can safely begin the Phase 1 shell only after route naming and the shared report-context shape are accepted.

Integration caution: current code exposes several ID-based accounting reads whose router signatures do not consistently include tenant context. The Product & Delivery Lead should route those endpoints through security/backend review before lender drilldown depends on them.

## Verification record

- `npm ci` completed from the pinned frontend lockfile. npm reported 26 dependency vulnerabilities (1 low, 4 moderate, 21 high); no automatic or breaking dependency update was applied.
- `npm run build` passed: TypeScript compilation and Vite production build completed. Vite reported a 1.80 MB main JavaScript chunk (535 kB gzip) and recommended code splitting.
- `npm run lint` is a pre-existing baseline failure: 227 findings (197 errors, 30 warnings) across the current frontend, dominated by `no-explicit-any` and React hook dependency findings. No lint code was changed as part of this audit.
- `git diff --check` passed before this verification section was appended; rerun at handoff.
