# Financial Reporting Rebuild — Master Tracker

**Status:** Active program; financial-reporting production release is **NO-GO**  
**Last updated:** 2026-08-13  
**Product owner:** Product & Delivery Lead  
**Scope:** Every business has an isolated accounting ledger, reports, exports, source evidence, permissions, and package history. Consolidation is a separate future capability and must never bypass entity or tenant isolation.

## Read this first after an interruption

1. Read this tracker for the current delivery state.
2. Confirm the exact candidate SHA and gate state below. A new SHA invalidates prior QA and Security decisions.
3. Do not push, deploy, access Railway, run migrations, run a backfill, or mutate production unless the listed gates authorize it.
4. Use the detailed source documents linked in [Program records](#program-records) for implementation requirements; this file is the coordination index, not a substitute for those specifications.

## Current delivery position

The settlement parser, settlement analytics, trailer replacement planning, and tracked startup migrations were delivered before this reporting rebuild. They do **not** make the platform lender-ready.

The finance program has completed discovery, accounting-policy guidance, architecture/API contracts, UX planning, QA criteria, and release/recovery planning. The ledger-only reporting rebuild, historical conversion, reconciliation, lender package, and staging rehearsal are not implemented.

### Immediate P0: accounting tenant isolation

| Item | Current state |
|---|---|
| Candidate | `a07201bc879499cce88343f629f3426e9dc14b67` in `/Users/sergio_m1_promax/.codex/worktrees/399d/elis-logistics-manager` |
| Backend self-verification | Auth-disabled focused `48/48`; production-shaped focused `48/48`; full backend `115/115` |
| Independent QA | **GO** for the exact SHA |
| Independent Security | **NO-GO** for the exact SHA |
| Integration | Not merged into `main` |
| Railway staging | Not authorized |
| Production | Not authorized |

### Security blockers on the active candidate

1. A tenant-local journal entry with a foreign settlement, repair, or depreciation source can still affect general-ledger and derived report totals.
2. A query-string `tenant_id` selector is silently accepted instead of rejected before resource work.
3. Starlette-level `404`/`405` and unhandled accounting `500` responses bypass the required canonical error envelope and request-ID correlation.

**Assigned action:** Security & Identity owns the bounded corrective patch, regressions, and a new isolated SHA. QA and Security must independently approve the replacement SHA before it may be integrated.

## Non-negotiable decisions

- A server-derived authenticated principal and server-owned tenant allowlist authorize access. `X-Tenant-ID` is a required selector only.
- Missing or invalid tenant context fails before data access. Foreign tenants or objects return generic non-enumerating `404` responses. Authorized permission denial returns `403`.
- Each confirmed legal entity/business has its own ledger and reports. No cross-tenant summing or consolidation without approved entity and elimination rules.
- The book ledger is authoritative for P&L, balance sheet, retained earnings, and cash flow. Operational vehicle, settlement, repair, and payoff-projection fields may link to evidence but must not override statement totals.
- Tax and lender views are separate, versioned layers over a frozen book snapshot. Cash basis, loan principal, and lender balances are never inferred from operational profit.
- Report readiness is `pass`, `block`, or `unknown`. Unknown blocks lender/package claims.
- Lender exports must be generated only from immutable completed report/package snapshots. The legacy mutable-table exports intentionally fail closed until this exists.
- Destructive accounting reset is permanently unavailable: authorized requests return `410 ACCOUNT_RESET_UNAVAILABLE` with zero financial-row changes.

## Delivery roadmap and evidence gates

| Phase | Outcome | Status | Exit evidence |
|---|---|---|---|
| 0 | Tenant authority and frozen API denial contract | In progress | New candidate receives QA GO and Security APPROVED; then isolated staging canary passes |
| 1 | Posting-event foundation and ledger revisions | Not started | Idempotent source/version postings; every journal entry balances; corrections reverse and replace rather than erase history |
| 2 | Opening balances, reconciliation, and historical conversion | Not started | Approved opening trial balance; bank, debt, assets, and equity reconcile; dry-run/backfill is idempotent and reversible |
| 3 | Ledger-only P&L, balance sheet, retained earnings, and cash flow | Not started | Financial equation and roll-forwards pass at each as-of date; no hybrid operational calculations |
| 4 | Debt, assets, depreciation, repairs, and schedules | Not started | Debt schedule equals ledger debt; asset schedule equals control accounts; lender evidence supports principal and interest |
| 5 | Reconciliation-first frontend and immutable package/export flow | Not started | UI shows scope, basis, cut-off, readiness, evidence, and `pass/block/unknown`; package/export parity passes |
| 6 | Migration/recovery, staging, and production release | Not started | Serialized migration job, backup/restore rehearsal, canaries, observability, and all financial QA gates pass |

## Financial reporting gate status

The baseline financial-reporting release remains **NO-GO**. None of the following may be assumed complete because a parser or individual journal entry works.

| Gate | Status | Required completion condition |
|---|---|---|
| Source-to-ledger reconciliation | NO-GO | Exact, idempotent, atomic posting and reversal evidence for settlements, repairs, assets, debt, depreciation, and adjustments |
| Balance-sheet equality | NO-GO | `Assets = Liabilities + Equity` to the cent for every entity and as-of date; no plug |
| Retained-earnings roll-forward | NO-GO | Beginning RE + income - distributions + prior-period adjustments reconciles to ending RE |
| Period cutoff | NO-GO | API, UI, exports, and ledger agree across timezone and recognition boundaries |
| Debt and depreciation | NO-GO | Lender-sourced principal/interest and asset/depreciation schedules reconcile to the ledger |
| PDF and Excel | NO-GO | Immutable-snapshot exports exactly match reports, are tenant-safe, and use valid numeric money cells |
| Tenant boundaries | In progress | P0 candidate plus independent QA/Security approval and staging evidence |
| Backfill | NO-GO | Dry-run, idempotent rerun, rollback/resume, control totals, and approved source evidence |
| Migration and rollback | NO-GO | Serialized migration authority, PostgreSQL rehearsal, backup/restore proof, and rollback/forward-repair plan |

## Required external decisions and evidence

Do not invent these inputs in the product.

1. Confirm legal entities, report scope, target lender/program, requested periods, and preparation language.
2. Establish accounting basis and controlled conversion/opening-balance date with a CPA/bookkeeper.
3. Reconcile bank, reserve, credit, receivable, payable, debt, asset, owner-equity, and tax balances to source records.
4. Obtain lender notes, payment allocations, current balances, rates, terms, maturity, collateral, and current/long-term classifications.
5. Confirm gross-versus-net settlement policy, reserve ownership, repair capitalization, trailer/intercompany allocations, and owner contribution/draw treatment.
6. Approve close roles, period-lock/reopen policy, report retention, review evidence, currency, timezone, and rounding rules.

## Ownership

| Owner | Responsibility | Current focus |
|---|---|---|
| Product & Delivery | Scope, sequencing, gate authorization, and handoffs | Hold release; resume from P0 Security remediation |
| Security & Identity | Authentication, tenant authority, object-level access, errors, exports | Fix the three active P0 blockers and return a new SHA |
| QA Gatekeeper | Independent adversarial testing and financial release evidence | Review the replacement Security candidate after it is delivered |
| Backend Integration | Posting services, ledger persistence, migrations, backfill, reports | Support Security patch; next is posting-event/ledger foundation after P0 GO |
| Frontend UI/UX | Reconciliation cockpit, statements, schedules, package flows | Waiting on stable reporting context, readiness contracts, and accounting inputs |
| Accounting Specialist | Policy, source evidence, chart of accounts, close and lender guidance | Policy baseline complete; CPA/lender/user evidence still required |
| Release & Reliability | Staging, recovery, migrations, observability, canaries | No Railway access until P0 QA + Security GO and explicit staging authorization |
| Architecture & API | Versioned contracts, ADRs, compatibility governance | Contract baseline complete; review breaking changes |

## Git and release state

- `main` is nine documentation commits ahead of `origin/main`.
- The active P0 candidate is isolated and not merged into `main`.
- There is no open PR for this program.
- Do not push `main` while it could trigger a deployment of the known-vulnerable baseline.
- Root `package-lock.json` is an unrelated untracked file. Do not stage, delete, or include it without separate confirmation.

## Program records

- [Accounting semantics audit](ACCOUNTING_SEMANTICS_AUDIT.md)
- [Architecture and target system](financial-reporting/current-and-target-architecture-v1.md)
- [Versioned API contracts](financial-reporting/api-contracts-v1.md)
- [Decisions and dependencies handoff](financial-reporting/decisions-dependencies-handoff.md)
- [Frontend UX audit and phases](frontend-financial-reporting-ux-audit.md)
- [Financial QA gates](qa/financial-reporting-qa-gates-2026-08-11.md)
- [Release and reliability runbook](RELEASE_RELIABILITY_RUNBOOK.md)
- [P0 non-production tenant-isolation checklist](P0_TENANT_ISOLATION_NON_PRODUCTION_RELEASE_CHECKLIST.md)

## Resume checklist

1. Read this tracker and verify the active candidate SHA with `git rev-parse` in its isolated worktree.
2. Read the latest Security and QA verdicts. Do not rely on approvals for an earlier SHA.
3. If Security returns a replacement candidate, verify its scope, then request fresh independent QA and Security review.
4. After both approve, update the P0 checklist with the exact SHA and prepare a reviewable integration branch or PR. Do not deploy.
5. Require explicit Product authorization before any named staging project, environment, service, database, or Railway action.
6. Only after P0 staging evidence is complete, start Phase 1 ledger/posting implementation.

