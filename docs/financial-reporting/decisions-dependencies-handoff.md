# Financial Reporting Decisions, Dependencies, and Handoff

Status: Product direction accepted; accounting-policy decisions remain gated
Prepared by: Architecture & API Contracts
Date: 2026-08-11

This register turns the target architecture into decisions and delivery dependencies. “Proposed” means implementation may prepare spikes and estimates, but the Product & Delivery Lead should resolve the decision before the dependent contract is marked stable.

## Architecture decision records

### ADR-FR-001: Ledger-only financial statements

Status: Accepted by Product direction and accounting-policy baseline

Decision: P&L, balance sheet, and cash flow totals come only from posted ledger revisions at a captured ledger watermark. Asset and debt schedules reconcile their subledgers to general-ledger control accounts. Operational tables may supply labels and links, not statement amounts.

Why: The current balance sheet combines ledger balances with truck fields and settlement/repair calculations. That can produce a balanced-looking response whose sources disagree.

Trade-off: Vehicle acquisition, debt, cash, and depreciation facts must be posted before target reports can replace current reports.

Rejected: Preserve hybrid calculations and add a warning. A warning cannot make the result reproducible or reconcile its sources.

### ADR-FR-002: Version basis, policy, and schema independently

Status: Accepted by Product direction

Decision: Persist `accounting_basis`, `accounting_policy_version`, and `report_schema_version` as separate fields on every report run.

Why: Recognition timing, accounting rules, and JSON shape change for different reasons. One version number cannot explain which meaning changed.

Trade-off: Product and support surfaces must display more metadata, and policy lifecycle needs an owner.

Rejected: A single API version. It cannot reproduce a report after a policy change that leaves the HTTP shape intact.

### ADR-FR-003: Accrual first; fail closed for cash basis

Status: Proposed, requires Accounting/Finance confirmation

Decision: The first stable policy supports accrual basis. `cash` remains a declared enum but returns `ACCOUNTING_BASIS_UNAVAILABLE` until cash receipt and payment events are complete and reconciled.

Why: Current “cash” behavior is an inconsistent proxy: some settlements post net profit directly to cash while per-asset settlements use receivables, and repairs always credit cash.

Trade-off: A requested cash-basis report may be unavailable in the first release.

Rejected: Derive cash basis from `net_profit` or `cash_settlement_amount` alone. It omits independent payments, timing, debt, and asset cash flows.

### ADR-FR-004: Immutable posting events and journal revisions

Status: Accepted by Product direction

Decision: Operational changes emit versioned posting events through an atomic outbox. Posted journal effects are append-only. A source correction reverses the prior active revision and posts a replacement.

Why: Current update flows delete and recreate journal entries. That loses accounting history and makes a past report impossible to reproduce.

Trade-off: Storage and query complexity increase; the system needs effective-revision views.

Rejected: Soft-delete plus replacement. Soft-deleted entries still do not describe the reversal date or preserve a clean accounting trail.

### ADR-FR-005: Asynchronous report-run resource

Status: Accepted by Product direction

Decision: All target reports use `POST /api/v1/accounting/report-runs`, even if a small run completes quickly.

Why: Reconciliation, snapshot capture, retries, exports, and auditability need a stable run identity.

Trade-off: Frontend handles queued/running/terminal states instead of one request/response.

Rejected: Synchronous GET reports with query parameters. They cannot safely own retries, snapshots, or export eligibility.

### ADR-FR-006: Package/export only from immutable completed snapshots

Status: Accepted by Product direction

Decision: A report package consumes completed report result checksums from one shared source cutoff plus persisted eligibility decisions. Rendering never recalculates a report or advances the cutoff. Any changed source or included report creates a new immutable package version.

Why: Current exports are separate calculations with no reconciliation gate. Screen and file can differ.

Trade-off: Users may wait for reconciliation or see a blocked export with remediation steps.

Rejected: Allow an “export anyway” button. That creates an authoritative-looking artifact from known-bad data.

### ADR-FR-007: Decimal strings at the API boundary

Status: Proposed

Decision: Public money fields are fixed-precision decimal strings with currency. Backend calculations use `Decimal`; generated frontend types keep amounts as strings until display or decimal-library arithmetic.

Why: Current APIs and frontend types use floats, which cannot exactly represent decimal money.

Trade-off: Existing formatting and chart code needs adapters.

Rejected: JSON numbers with documented two-decimal rounding. Representation error still occurs before rounding and encourages client arithmetic.

### ADR-FR-008: Server-authorized tenant selection

Status: Accepted and frozen by Security/Product; implementation prerequisite

Decision: Authentication derives the principal; the server derives its tenant allowlist and action permissions; `X-Tenant-ID` is a required selector only. Missing/invalid context returns 400 before data access. Foreign/unknown tenants and foreign/missing objects return an indistinguishable 404. A 403 means the principal is inside an authorized tenant but lacks the requested action. Every retained accounting/report/source/package/export route follows this invariant. Destructive accounting reset is unavailable.

Why: QA proved no-header disclosure plus cross-tenant account, journal, and ledger reads. A client-provided header is context, not authorization, and compatibility cannot preserve vulnerable route behavior.

Trade-off: Auth/session and repository scoping repairs must land before any target or retained legacy accounting surface can be released.

Rejected: Rely on unpredictable IDs, a caller-supplied tenant header, route-by-route optional dependencies, post-query authorization, or empty-result masking. None is an authorization boundary.

### ADR-FR-009: Separate accounting debt from profit-allocation forecasts

Status: Proposed, requires Product confirmation

Decision: The debt schedule reflects lender principal, draws, payments, interest, and accounting adjustments. Current profit-driven payoff replay remains an analytics forecast unless evidence establishes it as actual lender payment activity.

Why: The existing calculation reduces principal after cash investment recovery based on cumulative operating profit. That is a business allocation model, not proof that the lender received principal.

Trade-off: Product may show two balances during transition: book debt and an operational payoff projection, clearly labeled.

Rejected: Treat replayed payoff as the debt subledger. It can misstate liabilities and cash flow.

### ADR-FR-010: Asset register is distinct from vehicle operations

Status: Proposed

Decision: Create an accounting asset identity linked to, but not identical with, a truck/trailer/SUV record. Cost components, placed-in-service date, depreciation method, accumulated depreciation, and disposal belong to the asset subledger.

Why: Operational vehicle records can change over their lifecycle, while accounting basis and disposal history require append-only evidence.

Trade-off: Migration must establish a one-to-one initial link and define later split/combination cases.

Rejected: Keep all accounting fields on `Truck`. It couples report history to mutable operational state.

### ADR-FR-011: Contract-first frontend/backend governance

Status: Proposed

Decision: Check in the OpenAPI baseline, generate TypeScript financial-report types, run compatibility checks in CI, and require Architecture & API Contracts approval for breaking changes.

Why: Current frontend calls five accounting routes the backend does not implement and sends parameters that are ignored.

Trade-off: API changes need a deliberate review and generation step.

Rejected: Continue maintaining handwritten interfaces. Drift is already observable.

### ADR-FR-012: Reconciliation-first `/accounting` workspace and tri-state readiness

Status: Accepted by Product direction

Decision: `/accounting` is the canonical workspace. It resolves report context and shows readiness as exactly `pass`, `block`, or `unknown` before report/package actions. Existing report paths are aliases into this shell.

Why: The UI must distinguish a verified scope, a known failure, and an unresolved/unavailable evaluation. A missing response or unknown policy cannot look ready.

Trade-off: Existing standalone report pages become transitional aliases and require shared state handling.

Rejected: Binary ready/not-ready. It collapses policy uncertainty into either false confidence or an unexplained failure.

### ADR-FR-013: Explicit book, tax, and lender layers over one book snapshot

Status: Accepted as architecture; tax/lender policies remain unresolved

Decision: The book ledger is authoritative. Tax and lender layers apply separately versioned adjustments/presentation rules to the same frozen book snapshot. They never mutate or substitute book facts.

Why: Current code mixes book, tax depreciation, lender-style forecasts, and operational facts. Each output must state its layer and reconciliation bridge.

Trade-off: Tax and lender outputs remain unavailable until their entity, evidence, adjustment, and request profiles pass.

Rejected: Separate mutable ledgers for each view. They drift and obscure the bridge back to the books.

### ADR-FR-014: Effective-dated gross/net settlement templates

Status: Accepted as architecture; entity-specific template selection remains unresolved

Decision: Each legal entity/revenue stream uses one approved effective-dated `gross_principal` or `net_agent` posting template. Missing/overlapping/unapproved templates produce `unknown` and block affected packages.

Why: Principal-versus-agent treatment depends on contracts and economics, not tenant name or per-asset mode.

Trade-off: Settlement posting may pause while policy evidence is unresolved.

Rejected: Keep the current tenant-name branch. It encodes an accounting conclusion without evidence.

### ADR-FR-015: Source evidence, suspense, and period locks are readiness inputs

Status: Accepted by Product direction and accounting-policy baseline

Decision: Reports capture evidence-policy and period-lock versions. Required missing evidence, nonzero suspense, or prohibited period state produces `block`; unknown coverage/policy produces `unknown`. Locked periods accept only approved adjusting/reversing events through controlled reopen/open-period workflows.

Why: A balanced entry without support, resolved opening balances, or cut-off control is not package-ready.

Trade-off: Evidence capture and close workflow are first-class delivery scope.

Rejected: Treat these as checklist text outside the product. Export code could then bypass them.

## Dependencies

| ID | Dependency | Needed for | Owning role | Exit evidence |
|---|---|---|---|---|
| DEP-FR-001 | Confirm legal entities, base currency, and whether consolidated reports are required | Scope schema and account ownership | Product + Accounting/Finance | Signed scope matrix with sample tenants/entities |
| DEP-FR-002 | Confirm accrual recognition rules for settlements, repairs, reimbursements, reserves, trailer allocations, and cash adjustments | Accounting policy v1 | Accounting/Finance + Architecture | Rule table with effective dates and worked journal examples |
| DEP-FR-003 | Identify actual bank/lender cash events versus profit-allocation projections | Cash flow and debt schedule | Product + Accounting/Finance | Source-of-truth map and sample reconciled loan statements |
| DEP-FR-004 | Define asset capitalization, Section 179, bonus depreciation, MACRS conventions, disposal, and trailer replacement reserve treatment | Asset schedule and balance sheet | Accounting/Finance | Approved asset policy and sample roll-forward |
| DEP-FR-005 | Implement Security's frozen tenant invariant and repair every retained accounting/report/export route | All accounting surfaces | Security/Auth + Backend | Tests prove 400 missing/invalid, 404 foreign tenant/object, 403 in-tenant permission denial, no-header/cross-tenant account-journal-ledger denial, artifact denial, and reset unavailability |
| DEP-FR-006 | Select migration framework and register all historical/ad-hoc schema changes | New persistence and repeatable environments | Backend/Data | Fresh DB and production-clone migration tests produce the same schema |
| DEP-FR-007 | Inventory production posting coverage and duplicates without mutating data | Backfill and reconciliation baseline | Data/Backend + QA | Read-only variance report by tenant/source/month |
| DEP-FR-008 | Define accounting periods, close/reopen authority, and late-arriving event policy | Export gate and reproducibility | Product + Accounting/Finance | Period state machine and approval matrix |
| DEP-FR-009 | Choose report/export retention, artifact storage, and personally identifiable information policy | Export lifecycle | Product + Security/Infrastructure | Retention and access policy with deletion/expiry tests |
| DEP-FR-010 | Establish OpenAPI generation and compatibility tooling | Contract governance | Frontend + Backend + Architecture | CI fails on an unapproved breaking fixture and generated types compile |
| DEP-FR-011 | Create gold-standard report fixtures with accountant-approved totals | Implementation verification | QA + Accounting/Finance | Fixtures cover all five reports and every blocking reconciliation class |
| DEP-FR-012 | Decide legacy-route sunset milestones and customer communication | Compatibility | Product & Delivery | Usage thresholds, dates, rollback criteria, and owner |
| DEP-FR-013 | Approve entity eligibility for Schedule C/tax organizer and book-to-tax mappings | Tax layer/package | Accounting/Tax + Product | Entity election evidence, method/year, mapping version, adjustment bridge, reviewer approval |
| DEP-FR-014 | Approve source-evidence requirements and verification ownership by balance/report layer | Readiness and drilldown | Accounting/Finance + Product + Security | Evidence policy with required types, expiry, materiality, and access rules |
| DEP-FR-015 | Define settlement template effective ranges by legal entity/revenue stream | Posting and cutoff correctness | Accounting/Finance + Legal/Product | Signed gross/net decisions with contracts, dates, and representative postings |

## Delivery sequence and gates

### Gate 0: Contract decisions

Resolve ADR-FR-003, ADR-FR-009, ADR-FR-010, DEP-FR-001, DEP-FR-002, DEP-FR-013, DEP-FR-014, and DEP-FR-015. ADR-FR-008 is frozen and not open for reinterpretation. Output: stable v1 semantics, entity eligibility, evidence policy, and effective-dated posting templates.

### Gate 1: Persistence and authorization

First implement principal/allowlist authority, required selector validation, mandatory repository scope, protected caches/files, and reset removal across all retained routes. Then add migrations, outbox, posting events, revisioned ledger, and period/policy records. Output: adversarial tenant tests, exact-balance constraints, and idempotent posting tests.

### Gate 2: Shadow posting and reconciliation

Dual-run current side effects and target posting in shadow mode. Output: a read-only baseline with every variance explained or assigned. Do not replace current reports at this gate.

### Gate 3: Report parity

Implement report runs and all five schemas. Output: accountant-approved fixtures, cross-report equations, repeatable checksum at a fixed watermark, and load bounds.

### Gate 4: Frontend migration

Generate frontend types and implement the canonical `/accounting` workspace plus aliases. Output: user-flow evidence for `pass`, `block`, and `unknown`; queued/completed/failed run lifecycles; source cutoff display; tenant-safe drilldown; and package lifecycle states.

### Gate 5: Export enforcement

Enable eligibility and immutable package generation. Output: proof that `block`/`unknown` data cannot generate any artifact, package runs share one cutoff, and screen/file/package checksums reference stored results without recalculation.

### Gate 6: Legacy retirement

Publish deprecation headers, observe usage, then remove legacy adapters after the approved sunset gate. Rollback returns traffic to adapters, not to ungated legacy exports.

## Risks the Product & Delivery Lead should schedule explicitly

- Accounting sign-off is a delivery dependency, not final polish. Code cannot decide whether current operational events represent accrual, cash, reserves, principal, or owner distributions.
- Production migration history is incomplete in the startup registry. Estimation should include schema discovery against a production clone.
- Current reports may be materially different from target reports once ledger-only rules are applied. The UI needs a reconciliation/explanation plan, not only number parity.
- Debt and asset history may not contain enough evidence for an exact opening balance. The backfill plan needs explicit `verified`, `derived`, and `unresolved` provenance.
- Export blocking changes user behavior. Product copy and support remediation must ship with the gate.
- Current accounting reads have a QA-confirmed tenant disclosure. No retained account, journal, ledger, report, source, or export path is releasable until the frozen invariant passes adversarial tests.

## Handoff to Product & Delivery Lead

### What is ready

- A repository-grounded map of current sources, posting behavior, report APIs, frontend consumers, and contract gaps.
- A proposed v1 architecture with bounded contexts and a migration shape.
- Exact endpoint, tri-state readiness, source-cutoff, drilldown, run-state, report-result, error, compatibility, route-alias, and immutable-package contracts.
- Frozen tenant-authority semantics with adversarial tenant examples and reset prohibition.
- Fifteen ADRs and fifteen dependencies with exit evidence.

### Decisions requested

1. Assign Accounting/Finance authority for policy sign-off and gold fixtures.
2. Obtain accountant approval for accrual-first book policy and effective-dated gross/net templates.
3. Confirm whether profit-driven loan payoff remains analytics rather than book debt.
4. Approve entity-specific tax-organizer/Schedule C eligibility and the book-to-tax bridge before any `pass` state.
5. Set source-evidence ownership, period-close roles, and the legacy-route sunset dates. Tenant authority is already frozen as a release prerequisite.

### Recommended delivery tickets

1. Production-clone accounting schema and posting coverage inventory, read-only.
2. Mandatory tenant-authority middleware/repository repair for all retained accounting/report/source/export routes, plus destructive-reset retirement.
3. Accounting policy v1 workshop and worked posting examples.
4. Posting event/outbox and revisioned ledger technical design.
5. Reconciliation check registry and severity policy.
6. Asset and debt subledger source-of-truth design.
7. Report-run persistence and five result renderers.
8. OpenAPI generation, baseline diff, and frontend generated types.
9. Frontend report-run/reconciliation/export states.
10. Legacy adapter, deprecation, rollout, and rollback plan.
11. `/accounting` context/readiness shell, route aliases, and tri-state acceptance tests.
12. Immutable multi-report package manifest and snapshot-only renderer.

### Definition of ready for implementation

Implementation is ready to begin when the first six recommended tickets have named owners, ADR-FR-003/009/010 are resolved, Security's frozen ADR-FR-008 is represented by executable acceptance tests, and at least one accountant-approved end-to-end sample covers settlement, repair, cash, debt, acquisition, depreciation, P&L, balance sheet, and cash flow.

## Related

- [Current and target architecture](./current-and-target-architecture-v1.md)
- [API and schema contracts](./api-contracts-v1.md)
