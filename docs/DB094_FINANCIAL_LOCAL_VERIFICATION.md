# DB-094 financial integration — local verification

Date: 2026-10-30. Accountable owner: Backend & Integrations. Status: development implementation complete; release held. No production financial mutation, deployment, historical grant, credential installation, or temporary-record deletion occurred in this phase.

## Implemented

- One normal Maintenance & Repairs tile and source-linked Finance bill per uniquely matched source RO. Replay/concurrency preserves one cost; legacy duplicate imports are rejected.
- Final invoice cost dated by completion, then evidenced invoice date. No payment inferred from source status. Invoices create no Cash credit or reserve withdrawal.
- Verified partial payments and dated reserve withdrawals, append-only payment/reserve reversals, paid and remaining balance, owner original-receipt validation and reuse prevention. Shared Finance entry points enforce the same guards.
- Monthly/yearly incurred costs include periods without settlements; reserve metrics use actual payment/reversal dates and amounts. Archived repairs are excluded from ordinary lists, relationships and aggregates.
- Changed/cancelled invoices require review; unpaid correction/cancellation has compensating journals. Paid changes require payment correction review. Archived restoration remains guided and blocked.
- Customer-scoped complete financial manifest and durable HMAC wakeups, inbox, refetch worker, migrations and startup/shutdown lifecycle. Feature flags default off. Current source PDF is labeled as a current copy, not a preserved original.
- Temporary609 replacement remains preview-only. No archive execution or historical authorization expansion.

## Verification

- Final EDG full backend suite with disposable PostgreSQL: **689 passed**, 18 existing deprecation warnings, 20.61s. Includes real migration/concurrency tests.
- Final frontend Node suite: **80 passed**. TypeScript and isolated Vite production build pass; changed-source ESLint passed in the frontend handoff.
- Source full regression: **4720 passed, 419 skipped**, with two sandbox permission failures (loopback TLS socket binding and process-group inspection). Both exact failed tests rerun with required local permissions: **2 passed**. Affected source suites:176 passed in implementation handoff.
- Independent final QA: conditional development PASS;87 passed/3 PostgreSQL skipped in reviewer run, with root PostgreSQL evidence above. Final independent Security: development GO,77 EDG and28 source tests passed, no unresolved defect. Both reviewers made no implementation changes. One trailing-whitespace cleanup reported by QA was corrected; both repository diff checks pass.
- Synthetic API/PostgreSQL acceptance:15 repairs split603:6/609:9,15 bills,zero payments/reserve on import; replay unchanged. Existing58 synthetic repairs preserved. Verified200 partial payment on1000 yields paid200/due800 and200 withdrawal; reversal restores paid0/due1000 and zero net withdrawal.

## Explicit release holds

1. Browser acceptance remains **blocked, not passed**. CUA observed the local normal58-repair UI with sync controls inside Invoice review, but browser click failed before dispatch with “CDP operation exceeded its deadline before command dispatch.” Rebinding the fixture tab timed out/reset the runtime. Native fallback exposed a different user window and was not used to manipulate it. No import click or payment click was verified. Desktop/mobile changed-journey acceptance must be completed when control is functional.
2. Eight historical attributions remain unapproved. Trailer-tire cost-asset allocation, missing immutable source lines, ETS date/amount discrepancies and temporary609 mapping require reconciliation before selecting a financial batch. No initial15 financial batch is authorized for execution while these facts remain unresolved.
3. No financial PR/CI/merge/deploy occurred. Release requires exact-head protected CI, independent gate refresh if code changes, approved enablement/configuration, production migration/rollback checks and reconciliation acceptance.
4. Future delivery needs a separately approved signing-secret/configuration action. No signing credential was generated or installed. Financial import/worker and source delivery flags remain off by default.

Product outcome is not marked Done. The earlier deployed15 metadata-only history records remain separate from this undeployed financial phase.

## Reconciliation notes addition

Owner requested visible per-RO notes. The local implementation adds independently scoped append-only notes before or after financial import, visible on normal Repairs/VehicleDetail tiles. Source references, confirmed service-date decisions, original invoice dates and unexplained amount differences persist through replay/source changes; correction entries retain originals. Server-derived author/UTC time, scoped idempotency, full-history pagination, tenant-switch guards, and database/ORM update/delete protection are tested. Notes cannot grant access or change imported financial facts. Distinct migration2026_10_30_dieselbridge_reconciliation_notes upgrades databases that already applied the financial migration.

Final refreshed verification: **699 backend tests passed** with disposable PostgreSQL (23.33s), including8 note tests and2 additive migration tests (SQLite/realPostgreSQL). **85 frontend tests passed**, changed-file ESLint, TypeScript and production build passed. Independent incremental Security: development GO, no unresolved defect; QA: conditional development PASS (64 backend/5 frontend/TypeScript); browser acceptance remains unverified under the existing CUA blocker. No production action.

Two private owner-confirmed attachment payloads are prepared in task workspace db094-reconciliation-note-attachment-plan.json, not executed: RO46↔ETS1344, and RO45↔ETS1183 with owner-approved July13 completion. No amount difference explanation or historical payment inferred. These private decisions are not seeded into repository defaults. The current source still reports August31 for RO45; an audited source-date correction or tested reviewed override path is required before importing that RO with July13. Notes record the decision but do not silently apply it. Historical bill-to evidence/verification/grants remain separate required gates.
