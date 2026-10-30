# DB-094 settlement-aware release candidate

Development only, 2026-10-30. This plan authorizes no production action. Backend & Integrations accountable; high-risk lane. Source contract: sibling DieselBridge docs/contracts/db094-elis-repair-financial.md (v2 appendix). Consumer contract: DB094_FINANCIAL_IMPORT_DESIGN.md.

## Result

The source already stores cash settlement correctly. Its original invoice total can include the maximum conditional card surcharge; the old export did not expose actual settlement/payment facts. The v2 source manifest now retains quote/breakdown, canonical principal and complete privacy-limited payment-attempt observations separately. It never creates a settlement on read. Source settlement ledger transitions queue a signed amount-free refetch wakeup transactionally.

EDG recognizes full principal plus actually applied confirmed card fee/tax as cost, not the partial paid amount or maximum uncharged fee. It preserves the source quote and immutable observations. The synthetic source-produced RO41 fixture crosses the real source/consumer contract: quote5057.40, full cash obligation4886.38, charged card fee0, one4886.38 expense and zero automatic payments/reserve. A later actually charged fee requires review; pending/failed/reversed/refunded/inconsistent/overpaid observations do not invent cost or payment facts. Cash with positive source sales tax requires reconciliation under the owner's policy, never a blanket tax subtraction.

Tiles separately display quote, booked cost, source principal/gross receipts/methods/fees/pending/balance and EDG verified payments. Source confirmation timestamps are labeled recorded times; actual paid dates remain unknown unless independently evidenced. Source-attempt claims bind one whole confirmed gross receipt after fresh source validation and existing Finance date/funding/receipt/transaction verification. No split-source-receipt claims in this implementation. Exact retries and concurrent claims cannot duplicate withdrawal; local correction appends reversals and retains originals. Source reversals or changed claimed receipts require review and never silently reverse local funds.

The old invoice-only acceptance route rejects new records with any present service_fee_amount other than canonical0.00 (including malformed/null/falsy values), so a conditional surcharge cannot bypass settlement handling. Already accepted idempotent retries remain available. Reconciliation notes remain append-only and survive sync. Current source PDFs can retain quoted card fees and are labeled accordingly; no immutable original PDF claim.

## Local verification

Final EDG complete backend suite:726passed with disposable PostgreSQL,18 existing deprecation warnings,24.45s. Real SQLite/PostgreSQL prior-install upgrade tests preserve rows and enforce the partial unique source-claim index. Two concurrent PostgreSQL sessions with distinct receipts/keys claim the same source attempt: one payment/withdrawal, one duplicate rejection. Source-produced synthetic v2 fixture validates/imports/replays in EDG. Final frontend92tests, changed-file ESLint, TypeScript and Vite production build passed; isolated bundle index-Dhti-O53.js.

Fresh independent Security: development GO (84EDG/47source tests); legacy-guard review refreshed separately. QA: conditional development PASS (47source;24EDG with1PGskip then18PG-enabled;20frontendfocus; full-card/mixed partial arithmetic). Full source regression result is recorded in the source receipt after completion. Earlier run4740PASS/419SKIP had one test-only asynchronous relationship load failure; the test now explicitly awaits its order read rather than relying on identity-cache lifetime. No source product change was needed for that test correction.

Browser acceptance remains blocked: CUA rebind of the correct synthetic fixture tab/browser timed out20seconds and reset the runtime, after earlier before-dispatch click failures. No desktop/mobile import/payment acceptance is claimed. No live mutation or credentials were used to replace this missing gate.

## Coordinated release after holds are resolved

1. Complete synthetic desktop/mobile acceptance and exact-head independent gates. Publish focused source/EDG PRs only with current authorization; pass protected CI. Local commits are prepared, no publication performed here.
2. Obtain approval for this financial deployment and any separately specified webhook signing-secret/destination configuration. Earlier history-only approval does not release this held financial phase. Existing customer scope must not expand.
3. Keep ELIS_DIESELBRIDGE_FINANCIAL_ENABLED, ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED and DIESELBRIDGE_FLEET_WEBHOOK_DELIVERY_ENABLED disabled. Back up production under release procedures, verify target deployment states, deploy coordinated sourcev2/consumer and additive migrations. Consumer rejects v1 rather than reverting to ambiguous fee totals. Startup adds nullable source-observation/claim columns and a unique active-claim index; no historical financial rows are rewritten.
4. Smoke-test authorized read-only manifests, blocked historical billing metadata, exact version/hash agreement, tile/source-state reads, worker-off behavior and migration health. Configure the separately approved signing references; then explicitly enable the reviewed flow and verify signed duplicate/retry behavior in the approved scope.
5. Reconcile historical attributions, trailer cost asset, missing source-line evidence, owner-approved date corrections and temporary609 mapping before selecting the financial batch. Source date still differs for owner-approved July13/August5 cases: notes record decisions but do not change source/import dates. This fix does not grant the eight historical invoices or execute archive replacement.
6. Preview/reconcile/import an explicitly reviewed batch once, confirm one tile/cost per RO and replay unchanged, then separately verify each historical payment's actual amount/date/funding before reserve projection. Source confirmed cash is payment evidence, not proof of owner-personal versus business funding or cash handover date. Reconcile expense totals, actual withdrawal dates/amounts and dashboard/vehicle metrics; inspect future finalization/payment/correction sync.

## Rollback and stop signals

Disable delivery/import/worker flags first if unexpected cost/fee variance, scope leakage, duplicate active claim, migration failure or incorrect reserve movement occurs. Preserve inbox/outbox and immutable evidence; do not delete payments, notes, journals or migration columns. Restore a compatible deployment only after checking its manifest version and current data; older v1 consumer intentionally cannot consume sourcev2. Financial corrections require explicit reviewed compensating events, not database deletion or invoice rewriting. No production rollback was needed or attempted in this task.

## Remaining holds

Browser acceptance; historical attribution/date/asset/amount reconciliation; verified payment dates/funding; financial release/configuration approval; protected CI/merge/deploy and production verification. Feature flags default off. The user outcome is not marked Done.
