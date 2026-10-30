# DB-094 normal repair tiles and paid-only reserve integration

Status: **stable local implementation contract v1; no production execution, grants, credentials or deployment**. Architecture owner: financial_import_contract. Backend & Integrations accountable. Independent Security and QA gates remain required before release. This replaces the earlier alternatives-based draft. The local pure planner must be updated to this fixed policy before reuse.

## Fixed owner policy

- One current finalized DBN invoice per source RO becomes one normal `Repair` tile in Maintenance & Repairs / Invoice review, participating in existing repair-cost analytics. No second visible DBN history expense list.
- Recognize the **full final invoice expense**, after discounts and including invoiced tax, once. Use evidenced service completion date, otherwise evidenced invoice date. An import/creation timestamp is not proof of an original issue date. Missing both dates blocks apply.
- Repair reserve withdrawals occur **only for verified recorded payments**, including partial payments, on each actual payment date. Invoice receipt/finalization by itself creates **zero reserve withdrawal**. Negative reserve balances are allowed and never clamped.
- Record invoice cost without assuming payment. DBN workflow `paid` is displayed only as a source status; it supplies neither an EDG paid amount nor a cash transaction. Paid/due figures derive from linked active EDG verified payment commands.
- Future newly finalized authorized invoices automatically create normal repair tiles and their expense/bill projections. An invoice change, replacement or cancellation affecting an already booked RO creates review first and preserves the accepted amount until approved.
- Archive only explicitly reconciled temporary duplicates, retain original rows/evidence/postings and supply a reversible correction plan. No production deletions or archive execution in the current preparation task.
- Historical invoice/PDF access remains individually gated. The owner has requested a guided review, not granted eight historical export permissions.

There is no remaining invoice-versus-payment reserve timing choice: only `reserve_timing='recorded_payments'`, `reserve_date_basis='payment_date'`, `expense_date_rule='service_completion_else_invoice'`, `payment_inference='none'` are valid. Reject alternate policies with 422. A historical invoice can become a full-cost tile/bill with unknown historical payments and zero newly invented reserve withdrawal. Do not infer payments to make historical reserve metrics look complete.

## Source financial manifest — locked contract

`GET /api/v1/fleet-invoice-exports/repair-orders/financial`, existing read-only key and exact existing shop/customer scope. Retain operational eligibility from the existing complete history export: same customer/shop vehicle, completed/invoiced/paid RO, not internal/deleted, bounded 1,000 rows; reject oversized/partial results. No query filters. `Cache-Control: private, no-store`.

There is no RO current-invoice FK in the source. Select the unique active invoice using the existing partial uniqueness rule `status <> 'cancelled'` for the scoped RO. This set includes drafts: if the unique active invoice is draft, voided or otherwise ineligible, block the row; do **not** fall back to an older visible finalized predecessor. Assert uniqueness rather than picking newest by date. Cancelled/superseded invoice versions are not separate repair costs.

Response (all keys exact; nullable values explicit):

```json
{
  "version": "db094-repair-financial-v1",
  "shop_id": "uuid",
  "customer_id": "uuid",
  "complete": true,
  "count": 15,
  "snapshot_id": "sha256",
  "items": [{
    "repair_order_id": "uuid",
    "order_number": "TPS-...",
    "vehicle_id": "uuid",
    "vin": "VIN-or-null",
    "unit_number": "603-or-null",
    "description": "source-work-summary-or-null",
    "work_completed_at": "UTC-ISO-or-null",
    "service_date": "YYYY-MM-DD-or-null",
    "authorization": "authorized",
    "invoice": {
      "invoice_id": "uuid",
      "revision": "source-invoice-revision",
      "invoice_number": "invoice-number-or-null",
      "status": "current_finalized",
      "invoice_date": "YYYY-MM-DD-or-null",
      "invoice_date_basis": "native_issue_timestamp",
      "currency": "USD",
      "total_amount": "1000.00",
      "line_items": {},
      "pdf_sha256": null
    },
    "revision": "sha256-of-row-without-revision"
  }]
}
```

Allowed `authorization`: `authorized`, `attribution_required`, `not_finalized`, `unavailable`. For every non-authorized row `invoice` is **null**: do not leak inaccessible current financial IDs, totals, invoice dates, line items or PDF metadata through an operational grant. The response may still include all 15 authorized operational RO identities, with eight blocked financial subobjects. Source actor/owner inspection is not customer-key export authorization.

`service_date` is the UTC completion date only; missing completion remains null, rather than operational-history created-date fallback. `invoice_date_basis`: `native_issue_timestamp`, `preserved_issue_date`, or `unknown`. Only an evidenced invoice issue date is eligible as expense fallback. Imported/created-at metadata alone is `unknown`. Source may return `invoice_date:null` when unproven. `line_items` reuses the existing approved retail labor/parts projection, not raw snapshot wholesale; exclude internal costs, mechanic identifiers, private notes, supplier/contact information and unrelated payment data. PDF hash is present only for authorized preserved bytes; this route must not generate PDFs, reconstruct snapshots, backfill attribution or mutate source records.

Canonical SHA256 uses sorted compact JSON, ASCII escaping and UTF-8. Row revision excludes itself. Snapshot digest covers exactly `{version,shop_id,customer_id,items}` including row revisions; count/complete/snapshot_id excluded. Monetary values are nonnegative two-decimal strings; consumer initially supports USD only and blocks other currency. Invoice status is the neutral `current_finalized`. Its revision is the canonical digest of the displayed authorized invoice fields excluding revision; raw payment status, paid_at and Invoice.updated_at are excluded, so recording source payment alone does not invent EDG payment or trigger spurious cost-change review. The invoice object is the exact unique active invoice, independently checked against billing/export authorization. Snapshot materialization must consistently attest that relationship rather than joining independently changing loosely paginated histories. The accepted immutable observation is recorded; a later source change is a review event, not a claim that a cross-app transaction froze the source.

Category is derived from authorized invoice/work evidence in the consumer, with an explicit category decision for ambiguous work. Never default all jobs to `maintenance`: dashboard treats that category as PM. Operational VIN assignment and economic cost asset are separate: INV000023's six trailer tires need cost-asset confirmation even if the RO belongs operationally to truck609.

## Backend models — locked names and responsibilities

Add these in Backend-owned `backend/app/models/dieselbridge.py`, with an additive idempotent migration integrated by root. Store UUID event/evidence IDs using the existing Finance model conventions; use Numeric(18,2) or integer minor units for money, not float.

1. **`DieselBridgeRepairLink`** (`dieselbridge_repair_links`): integer id; tenant_id FK; source_system default dieselbridge; shop_id; customer_id; repair_order_id; repair_id FK unique; operational_truck_id FK; cost_asset_id FK; accepted_invoice_id/revision; accepted_manifest_id; accepted_total; currency; expense_date; expense_date_basis; category_basis; source_evidence_id FK FinanceEvidence; bill_event_id FK FinanceEvent.id nullable for true-zero cost; state (`accepted`, `review_required`, `source_unavailable`); pending_source JSON nullable; payment_history_confirmed bool default false; created_at. Unique `(tenant_id,source_system,shop_id,repair_order_id)`. Invoice number is not identity. Existing accepted assignment cannot silently move trucks/customers. A recorded historical-total packet cannot set financial authorization.
2. **`DieselBridgeRepairPayment`** (`dieselbridge_repair_payments`): integer id; tenant_id; repair_link_id FK; finance_payment_event_id FK unique; amount; paid_on; payer; transaction_id nullable; evidence_id nullable; reserve_withdrawal_id FK nullable when outside the retained 2026 reserve regime; reversal_event_id FK nullable; reserve_reversal_id FK nullable. Each active Finance payment for the canonical DBN bill has at most one reserve projection. The wire payment date is `paid_date`; wire reversal date is `reversal_date`. Reversal references immutable Finance history; do not delete payment evidence.
3. **`DieselBridgeFinancialOperation`** (`dieselbridge_financial_operations`): UUID id; tenant_id; connection_slug; action; idempotency_key; request_digest; plan_digest; result JSON; created_at. Unique `(tenant_id,connection_slug,action,idempotency_key)`. Same key/content returns original receipt; same key/different content is409. One transaction persists the completed operation and all results.
4. **`DieselBridgeFinancialInbox`** (`dieselbridge_financial_inbox`): integer id; tenant_id; connection_slug; event_id; body_digest; payload JSON; received_at; processed_at nullable; attempts; last_error_code nullable; operation_id nullable. Unique `(tenant_id,connection_slug,event_id)`. An authenticated event is a durable wake-up, not authority to book payload facts. Worker refetches the manifest. A changed-body replay with the same ID is409.

Root owns the archive model, active-repair filtering, registrations and migration integration. A proposed archive must preserve complete original row/evidence/payment/reserve/journal snapshots and immutable links, not turn existing costs to zero or delete rows. Backend supplies archive **preview** effects only in this phase. No archive apply route is enabled until the guided mapping and replacement plan are approved.

## Finance engine and reserve behavior

For a newly eligible authorized finalized RO: create normal `Repair` with full accepted cost/date/category, preserve source FinanceEvidence, and call existing `finance.append_command` with `Command(kind='bill', legacy_repair_id=repair.id, asset_id=cost_asset_id, category='repairs', amount=total, evidence_id=source_evidence_id, source_ref='dbn-ro:<shop>:<ro>:<accepted-revision>')` at expense date. This debits Repairs and credits Payable, with no Cash credit. Zero-cost finalized evidence produces a zero-cost tile and no positive-money bill/payment. Preserve no-charge facts as evidence, never nominal $0.01 expenses.

Do not call generic repair-create/update/delete helpers or the legacy `create_repair_journal_entry`, which currently credits Cash. Root supplies a compatibility adapter for legacy reports: DBN source-linked repairs are represented once in normal cost analytics and their authoritative Finance bill/payment path; legacy journal surfaces must either read the linked Finance postings or use a source-linked non-cash accrual mirror, never a second independent charge. The first implementation may omit a legacy journal mirror if no affected report requires it, but must state that limitation and test the affected reports. Generic repair edit/delete must reject source-linked financial rows and direct corrections through review.

For a verified payment: use the existing `finance.append_command` payment contract against **the canonical link's bill_event_id**, on actual paid date. Existing Finance rules require reconciled transactions for business/card/cash and explicit qualified evidence for owner payment. Do not weaken them or trust a client `verified:true`. Retain account/funding evidence. Payment amount must be positive, at most remaining recorded obligation, and not in future. Existing closed-period/dependent-posting checks apply. Root handles existing `business_funds` compatibility without bypassing verification.

Project that accepted Finance payment once to `RepairReserveLedger` using `source_type='dbn_payment'`, `source_id=DieselBridgeRepairPayment.id`, `entry_type='withdrawal'`, actual payment date/amount and cost asset. Keep the existing reserve regime start2026-01-01; prior paid facts remain visible but do not fabricate 2026 withdrawals. The invoice itself does not project a withdrawal. Owner reimbursement/card-principal repayment is not a second repair payment: project only payments whose claim_id is the link's original canonical bill, never the reimbursement claim created by an owner payment.

Generic Finance payment/reversal entry points must invoke the same projection helper, not just the new DBN-specific route. Otherwise recording a legitimate payment elsewhere would leave reserve stale. Root owns the Finance command hook; Backend exposes idempotent `project_verified_repair_payment(db, tenant, event)` and `project_verified_repair_payment_reversal(db, tenant, reversal_event)`.

Payment reversal appends the existing Finance reversal command after its dependency/period checks, then appends one positive reserve `withdrawal_reversal` linked to the original withdrawal; retain both originals. Root owns ledger enum/check/migration/balance/filter integration. Net withdrawals = withdrawals minus linked withdrawal reversals; balance = deposits + manual adjustments - net withdrawals. Do not put a payment reversal in manual adjustments. Repeated or concurrent reversals create no second financial/reserve effect. A later approved re-payment is a new verified payment event.

## EDG routes and JSON — locked contract

Base prefix `/api/v1/accounting/dieselbridge`. Reuse strong `accounting_tenant` authentication and same server-managed connection origin/customer scope. Tenant/shop/customer may not be overridden by request body. Every referenced repair, bill, transaction, evidence and payment is tenant-checked. Cross-tenant/missing objects return404 without disclosing existence. Router owns commit/rollback; sync handlers run blocking locks/HTTP in worker threads.

### Financial preview/sync

`POST /connections/{slug}/financial-import/preview` is read-only. Request `{version:'db094-financial-import-v1', repair_order_ids?:string[], decisions?:[{repair_order_id,cost_asset_id?,category?,legacy_repair_ids?:int[]}]}`. Decisions must be server-reconciled; client booleans cannot authorize source access or assert verified payments. Default initial batch is all selected operational RO rows, not silently just the seven authorized invoices. Explicit smaller selection is supported for a separately approved narrower batch.

Reply exact envelope:

```json
{
  "version":"db094-financial-import-v1",
  "plan_digest":"sha256",
  "source_manifest_digest":"sha256",
  "local_state_digest":"sha256",
  "executable":false,
  "execution_enabled":false,
  "rows":[{
    "repair_order_id":"uuid","order_number":"TPS-...","repair_id":null,
    "action":"blocked","truck_name":"Volvo609","source_revision":"sha256","invoice_id":null,
    "invoice_total":null,"currency":null,"operational_truck_id":1,"cost_asset_id":1,
    "repair_date":"2026-04-20","repair_date_basis":"service_completion",
    "category":null,"expense_delta":null,"reserve_delta":"0.00",
    "recorded_paid_amount":"0.00","recorded_balance_due":null,
    "payment_history_confirmed":false,"payment_status":"unconfirmed",
    "replacement_proposals":[],"blockers":["financial_access_required"]
  }],
  "summary":{"source_count":15,"create":0,"unchanged":0,"review_required":0,"blocked":15},
  "effects":{"expense_delta_by_asset_month":[],"reserve_delta_by_asset_date":[],"negative_balances":[]},
  "blockers":[]
}
```

`action` is `create`, `unchanged`, `review_required`, `blocked`. Unauthorized financial fields remain null, not zero. A valid new invoice has full-cost expense_delta and reserve_delta0. `recorded_paid_amount`/`recorded_balance_due` explicitly describe EDG recorded activity, not verified complete real-world history. Status is `unconfirmed` with no confirmed payment facts, `partial` after recorded amount between0 and total, `paid` only when recorded verified amounts satisfy accepted total. Display the history caveat until confirmed; source `paid` cannot switch this status. Existing payments and full original bill stay stable across unchanged replay. Changed/cancelled source has no new cost/reserve delta and enters review.

Canonical plan digest uses sorted compact ASCII-escaped JSON/UTF-8 and includes exact server scope, fixed policy version, immutable source manifest, accepted local links/repair/evidence/payment/ledger state digests, explicit cost-asset/category/replacement decisions and proposed effects. Exclude volatile observation timestamps and all credentials/signed URLs. Regenerated invoice IDs cannot create a second RO link.

`POST /connections/{slug}/financial-import/sync` uses the same request plus `plan_digest`, `source_manifest_digest`, `local_state_digest`; requires `Idempotency-Key`. Proposed reply `{version,operation_id,status:'applied'|'already_applied',created_repair_ids,unchanged_repair_ids,review_required_repair_ids,blocked_repair_order_ids,source_manifest_digest}`. Root supplies an execution guard defaultfalse for this local task; disabled mutation returns409 `EXECUTION_DISABLED` with zero writes. There is no production enablement approval. Once enabled after release approval, complete initial selected batch is atomic: block any unknown access/date/cost asset; do not partially charge7 of15 by default. Background processing of a new single authorized finalized event can run its single-RO batch under the previously approved automatic policy.

Refetch/validate source, acquire existing tenant advisory lock and deterministic affected-row locks, recompute local digests, reject stale plans409, persist canonical repair/evidence/bill/source link/operation atomically. Avoid unbounded PDF work under the write lock. Source observation and local commit are not a distributed transaction; record the exact accepted immutable revision and process later changes as review events. Roll back all local effects on any failure.

### Financial state used by existing tiles

`GET /repairs/{repair_id}/financial-state` replies `{repair_id,source_system,repair_order_id,order_number,invoice_id,invoice_number,accepted_revision,state,source_status,invoice_total,currency,repair_date,repair_date_basis,operational_truck_id,cost_asset_id,category,recorded_paid_amount,recorded_balance_due,payment_status,payment_history_confirmed,payments,review_reason,can_record_payment,can_edit,can_delete}`. Source-linked `can_edit`/`can_delete` arefalse; use correction review. `payments` items `{id,amount,paid_on,payer,evidence_id,transaction_id,status:'active'|'reversed',reversal_event_id}`. No credentials, secret refs or cached inaccessible PDF URL.

Bulk `GET /repair-financial-states?truck_id=<optional>&after=0&limit=100` replies `{items:[<same-state-object>],next_after}` scoped to linked normal repairs; limit1..500. Frontend merges by normal repair_id; it does not render a second DBN repair list. Individual scoped absent/unlinked ID returns404. Existing normal `/repairs` list remains canonical tile list.

### Verified payment and reversal

`POST /repairs/{repair_id}/verified-payments` body `{amount:'100.00',paid_date:'2026-10-30',payer:'business'|'owner'|'card'|'cash',transaction_id?:string,evidence_id?:string,expected_revision:string,owner_payment_confirmed:false,note:string(min3)}` and `Idempotency-Key`. Owner payments additionally require `owner_payment_confirmed:true`, a preserved independent payment receipt and the explicit note; the source invoice alone is insufficient evidence. Other payers reject owner attestation. Server resolves accepted bill/link, verifies all facts via existing Finance engine, applies payment+one reserve projection in one tenant-locked transaction. Reply `{operation_id,payment_id,finance_event_id,reserve_withdrawal_id,financial_state:<state-object>}`. All money strict positive decimal-cent strings, dates actual evidenced paid dates. Reject overpayment, stale accepted revision, missing verification, wrong account type/scope, future date, review-required/cancelled invoice, closed period and duplicate content conflict.

`POST /repairs/{repair_id}/verified-payments/{payment_id}/reverse` body `{reversal_date:'YYYY-MM-DD',reason:string,expected_revision:string}` and `Idempotency-Key`. Reply `{operation_id,payment_id,reversal_event_id,reserve_reversal_id,financial_state}`. Validate exact link/tenant and immutable Finance reversal rules, then append compensation once. No payment deletion and no fake bank refund. Identical retry returns original result.

### Archive preparation only

`POST /connections/{slug}/financial-import/archive-preview` body `{repair_order_id,legacy_repair_ids:[123,125,126],reason,expected_source_revision}`; no persistent writes. Reply `{executable:false,execution_enabled:false,plan_digest,replacement_candidates:[{repair_id,match_basis,cost,original_date,reserve_entries,journal_entries,payment_evidence,proposed_archive,blockers}],effects,blockers}`. IDs are explicit guided selections, not title-based matches. Root owns archive execution contract/implementation later; no delete/archive mutation endpoint in this preparation release.

401 unauthenticated;403 unauthorized financial action;404 scoped object absent;409 stale state/review/idempotency/execution disabled/closed period;422 invalid money/date/policy/body;502 invalid/incomplete source manifest. Errors disclose no secrets or cross-tenant data.

## Exact future finalization wake-up contract

Source: durable outbox in invoice finalization/change/cancellation transaction; sender retries with backoff and acknowledges only successful durable receiver acceptance. Source must select only the configured customer's eligible export scope; current RO assignment cannot broaden billing access. EDG inbox wakes a worker to refetch financial manifest; payload facts never directly book an expense/payment.

POST `/api/v1/accounting/dieselbridge/webhooks/{slug}` raw UTF-8 JSON body exact keys:

```json
{"version":"db094-financial-wakeup-v1","event_id":"uuid","shop_id":"uuid","customer_id":"uuid","repair_order_id":"uuid","kind":"invoice_finalized","occurred_at":"UTC-ISO"}
```

`kind`: `invoice_finalized`, `invoice_changed`, `invoice_cancelled`. No invoice IDs, amounts, revisions, contacts or payment facts. Headers `X-DBN-Event-Id` equals body event_id; `X-DBN-Timestamp` is Unix integer seconds; `X-DBN-Signature` is `v1=` plus lowercase HMACSHA256(secret, timestamp + '.' + exact_raw_body_bytes). Verify constant-time, strict fields/UUID/time/scope, timestamp within±300seconds and HTTPS destination. Re-sign a retry with current timestamp while keeping body/eventID stable. Durable inbox unique tenant/slug/eventID plus bodydigest; identical duplicate202 `{status:'accepted'|'duplicate',event_id}`; changed-body replay409. Verify signature before exposing duplicate state. No browser cookies substitute for sender authentication.

Sender/receiver use separately approved server-managed secret references, never reuse the read-only invoice API key as signing secret. Missing secret/config failsclosed (receiver503 `WEBHOOK_NOT_CONFIGURED`, sender no transmission). Do not create/configure credential values in this task. Persist/retry outbox failures; signed notifications only schedule refetch. Worker claim/ack is durable; crash after financial commit then repeat is harmless by source/operation identities. Invalid/revoked authorization blocks processing. New finalized RO can auto-create unpaid bill+tile after policy/transport release approval; accepted revision change/cancellation produces review and preserves booked effects. No automatic archive or historical grant.

## Reversible temporary truck609 replacement facts

Strong matches: ID123 NOx/heating2026-03-21, ID125 steer tires2026-03-27, ID126 batteries2026-04-18. All currently null-cost, with zero reserve/journal effects. Preserve row/evidence snapshots and eventually archive only their explicitly confirmed component mapping to ETS-0386-97052. The new ETS normal tile cannot be financially created until its attribution/source evidence policy is resolved.

Preserve ID136 cleaning2026-03-30 ($150; withdrawal73/journal514), because the charge is absent from the immutable invoice snapshot despite RO summary text. Preserve ID114 diagnostic2026-02-26 ($202.80; withdrawal33/journal395), which has independent invoice4076 and business-Zelle payment confirmation. Neither is proven temporary duplicate. Do not subtract352.80 from expenses or reverse their reserve/journals without contrary evidence and explicit per-ID confirmation.

For any subsequently approved positive-cost replacement, retain original journals/reserve entries and append linked bookkeeping/reserve reversals rather than delete history. Distinct `withdrawal_reversal` keeps net withdrawals accurate without masquerading as manual adjustments. Reactivating originals requires a reviewed compensating operation that first prevents both original and replacement expense from being active. All dependent payment/closed-period checks remain enforced.

## File ownership before parallel implementation

| Owner | Exclusive files / responsibilities |
| --- | --- |
| Architecture (this task) | `docs/DB094_FINANCIAL_IMPORT_DESIGN.md` only; stable contract and policy clarifications. |
| Backend agent | Existing `backend/app/models/dieselbridge.py` and `routers/dieselbridge.py`; new `schemas/dieselbridge_financial.py` and `services/dieselbridge_financial.py`; `services/repair_history.py`, manual managed-repair guards in `routers/repairs.py`; dedicated migration helper/new migration resource if coordinated with root; `tests/test_dieselbridge_financial.py` and dedicated PostgreSQL cases. Financial manifests/read validation, bill/source/payment models, preview/sync, state endpoints, verified-payment/reversal helpers, signed inbox/durable receiver worker hooks. Expose helpers for root hooks; do not edit root-owned shared files concurrently. |
| Frontend agent | Existing normal tile integration in `frontend/src/pages/Repairs.tsx` and `VehicleDetail.tsx`, typed API additions in `frontend/src/services/api.ts`, new focused payment/state/sync control components under `components/repairs`, focused tests. Remove standalone DBN history list after replacing it with a compact source sync/review control; render financial state inside canonical existing tiles. Existing expense list remains authoritative. |
| Source agent | New current-financial manifest endpoint, source outbox model/migration/sender and source finalization/change/cancellation event hooks, scoped source fixtures/tests and source contract documentation. Coordinate source router registration with root; no grants/credential creation. |
| Root integration | `app/main.py`/router and model registrations, shared migration_runner integration, existing pure planner fixed-policy update, `Repair` archive model/active filters, analytics/report/reserve reversal projections, legacy journal compatibility, `finance.py` payment/reversal hook and business_funds compatibility, source/root registration conflicts, project board, release integration. Shared tests modified only with explicit handoff. |

Frontend must not call generic repair Edit/Delete for source-linked rows or record unverified payment booleans. Show full cost, service/invoice date provenance, source invoice/PDF via existing guarded proxy, recorded paid amount/balance/history caveat and review state. Payment dialog collects real date/amount/funding/evidence or matched transaction and displays resulting reserve movement before save. Pending attribution/cost-asset/category issues are review controls, not fabricated zero-cost tiles. Invalidate normal repairs, review coverage, source state, dashboard/vehicle analytics and reserve queries after successful mutations. Preserve tenant switches and stale-response guards.

## Acceptance gates

1. Missing/partial/wrong-scope source snapshots or non-current/draft/voided financial documents create no cost. Blocked8 expose no unauthorized financial fields. Current active invoice selection never falls back to an older visible predecessor.
2. Exactly one active normal repair/source link/bill per RO under replay/concurrency; invoice regeneration does not add a second cost. Cost asset confirmation is independent of operational VIN for trailer work. No duplicate source history expense list remains.
3. Full cost uses completion then evidenced invoice date. No fabricated import date. Correct categories keep actualPM distinct from transmission/tires/other repairs. Missing facts block rather than guess.
4. Invoice finalization creates **zero reserve withdrawal and zero Cash credit**. A verified100 partial payment on1000 creates one100 withdrawal, recorded paid100 and recorded balance900. Later verified900 creates one900 withdrawal and zero balance. Repeated calls/events create no extra movement. Negative reserve balance stays visible. Historical unknown payments remain unconfirmed and unprojected.
5. Existing Finance business/card/cash transaction verification, owner evidence, tenant, remaining-obligation, dependent-payment and closed-period checks cannot be bypassed. Owner reimbursement/card repayment does not withdraw reserve a second time. Generic Finance entry points use the same DBN projection helper.
6. Reversal retains originals, appends one Finance reversal and one linked reserve reversal, restores recorded balance, and preserves manual-adjustment totals. Replay/concurrency and failure-after-each-write tests prove all-or-nothing behavior.
7. Archive preview for123/125/126 preserves all evidence and shows zero prior financial reversal. Preserve136/114 and their352.80 effects. No archive/delete execution in current preparation. Later positive-cost replacement/restoration is separately tested and reviewed.
8. Existing normal tile list/review coverage, per-truck/month/year costs, individual repair chart, all-in cost per mile, PM status, net withdrawals/balance and exports reconcile using active repairs and source-linked Finance effects once. Settlement take-home and accrual repair profit are not double-subtracted. Unrelated repairs/trailers remain unchanged.
9. Source revision changes/cancellations mark review, keep accepted amounts, and do not silently reverse paid facts. Access removal withholds source data without deleting booked audit history.
10. Signed wake-ups verify exact bytes/time/scope/replay, persist inbox before ack, survive worker crash/retry, and never import payload amounts. Missing signing config is disabled/failclosed; no credentials are generated. Future newly finalized invoice becomes a normal unpaid tile only after explicit release enablement.
11. TDD local implementation, PostgreSQL concurrency/rollback, independent Security/QA, focused PR/CI and signed-in desktop/mobile runtime acceptance precede release. Current task creates no production financial writes, grants, secrets, archive or deployment. Initial15 financial batch remains blocked until all selected historical attributions/cost-asset facts are reconciled and approved; a smaller batch requires explicit reviewed selection.

## Local preparation evidence

The pure preview builder (`backend/app/services/dieselbridge_financial_plan.py`) now enforces the fixed recorded-payments/payment-date policy. The local implementation also includes normal repair tiles, source-linked Finance bills, verified partial-payment and reversal projections, migration/lifecycle registration, scoped manifest transport, durable signed wake-ups and unpaid amendment/cancellation review. Both financial import and worker feature flags default off. Temporary-record archive execution and historical access grants remain outside this release. See `DB094_FINANCIAL_LOCAL_VERIFICATION.md` for final checks and explicit release holds.

Owner-scoped read-only inspection subsequently establishes eight historical gross totals11,810.06 and all15 gross19,879.70 before reconciliation. All8 still lack attribution evidence/mapping; no grant approved. INV000023 lists six trailer tires and needs cost-asset confirmation. INV000006 lacks an immutable line snapshot. ETSINV0718 remains blocked by the imported-ETS historical-attribution guard.

The exact609 effects audit finds strong temporary components123/125/126, all currently null-cost with zero reserve/journal effects. Preserve cleaning136($150; withdrawal73/journal514), because its charge is absent from the invoice snapshot despite RO description. Preserve diagnostic114($202.80; withdrawal33/journal395), with independent invoice4076 evidence and business-Zelle paid confirmation. Do not net352.80 without contrary duplicate proof.

## Append-only reconciliation notes (2026-10-30)

Owner requests durable notes on each RO. Notes are local owner reconciliation evidence, never source authorization, payments or date/amount overrides. `dbn_reconciliation_notes` keys tenant/slug/shop/customer/sourceRO independently of financial Link, so notes can be attached to an existing scoped operational history row before invoice eligibility and automatically appear on the normal tile when imported. Append-only ORM and database guards retain every prior entry; corrections append `supersedes_note_id`, constrained to the same scoped RO. Sync never edits/deletes notes.

POST `/connections/{slug}/repair-orders/{repair_order_id}/reconciliation-notes` or `/repairs/{repair_id}/reconciliation-notes`, authenticated accounting tenant + `Idempotency-Key`. Body exact `{note:string(3..4000), source_references:string[](max10, each1..300), confirmed_service_date?:YYYY-MM-DD, original_invoice_date?:YYYY-MM-DD, amount_discrepancy?:string(max1000), supersedes_note_id?:positiveInteger}`. All text trimmed and bounded, unknown fields rejected. Server derives source identity from uniquely scoped Link or existing scoped operational history; derives author from authenticated configured principal (local development explicitly labeled), and records UTC creation timestamp. Same key/body returns original note; changed body409; invalid target404; wrong supersession409. Tenant serialization prevents duplicate appends. No update/delete routes. GET either route paginates `{items:[{id,note,source_references,confirmed_service_date,original_invoice_date,amount_discrepancy,supersedes_note_id,created_at,author,repair_order_id}],next_after}` by ascending immutable ID (limit1..100). Financial state includes `reconciliation_notes` latest100 in chronological order and `reconciliation_notes_has_older`; use paginated GET for complete history. UI renders notes as plain text, visibly labels reference-only dates/discrepancies and retained corrections, allows appending notes with a retry-stable key, guards tenant switches, and can load older entries. No client-selected actor or permission change. Metadata-only append works with financial import flags off; no feed fetch, grant, cost/payment or reserve effect. Server ownership/scopes remain enforced even if note bodies mention other records.

Acceptance: pre-import note survives import/replay/source correction/cancellation and remains linked by sourceRO; cross-tenant/customer/RO and spoofed author rejected; correction retains original; raw SQL/bulk mutation denied; exact retry single row, conflicting key409, failed transaction leaves no row; dates remain informational until separately reviewed correction, no finance/reserve writes. Desktop/mobile browser acceptance and independent gates must be refreshed for this addition before release.

## Settlement-aware cost and actual-payment observations v2 (2026-10-30)

This supersedes the v1 rule that booked the raw stored invoice.total_amount unconditionally. Normative source schema is locked in DieselBridge `docs/contracts/db094-elis-repair-financial.md`, section “Settlement-aware manifest v2”. Same endpoint, exact version `db094-repair-financial-v2`; reject v1 because it cannot prove conditional fee composition. No source grants or production changes. Invoice gains exact breakdown{subtotal,shop_supplies_amount,service_fee_amount,tax_amount,discount_amount}; row gains nullable settlement with independently hashed observed payment attempts. Raw quote remains retained as source_invoice_total. Non-authorized rows expose neither invoice nor settlement. No invoice rendering or source mutation.

Source settlement shape is exact: {settlement_id,revision,status:available|review_required,review_reasons:[],source_state,principal_total,max_card_fee,max_card_fee_tax,confirmed_principal,pending_principal,unapplied_credit,refund_pending,payments:[{attempt_id,revision,rail,state,principal_amount,received_amount:null|money,gross_received_amount:null|money,applied_principal_amount,applied_card_fee_amount,applied_card_fee_tax_amount,unapplied_amount,confirmed_at:null|UTCISO,actual_paid_date:null|date,paid_date_basis:unknown|explicit_verified_date}]}. All money nonnegative two-decimal strings; rails cash/card/zelle/check/ach/fleet_payment; states pending/confirmed/failed/expired/refunded/reversed. Source_state unpaid/payment_pending/partially_paid/partially_paid_pending/paid/overpayment_resolution. At most1000 attempts per invoice; complete joined snapshot bounded10000. No provider/private receipt/contact/actor/internal processor-cost fields. Existing source received_amount and legacy Payment.amount are principal-only; **gross_received_amount is the actual historical charged/received total** (confirmed/refunded/reversed card provider_charge_amount, non-card received_amount); pending/failed/expired gross is null. A reversed/refunded historical charge is not current paid money or a verified refund.

For available internally consistent source facts, repair expense = **full settlement principal_total + sum applied card fee and applied card-fee tax on confirmed attempts**. The whole principal is incurred even when source only received a partial payment. Uncharged maximum surcharge is excluded. Missing settlement may use raw total only if the v2 breakdown proves service_fee_amount0 and arithmetic is consistent. Unknown fees, contradictory aggregates, refund/reversal/overpayment/unapplied facts or cash with positive source sales tax require review; do not silently strip taxes. Owner policy excludes card surcharge and sales tax for these cash payments; it does not authorize inventing tax exemptions or editing finalized invoices.

RO41 acceptance: raw quote5057.40 = subtotal4844.38 + supplies42.00 + max card fee171.02, tax0. Confirmed cash settlement principal4886.38 and actual fee0 produce one4886.38 repair cost/bill, preserve171.02 quote variance, and **zero automatic EDG payment/reserve withdrawal**. Source confirms cash receipt, not owner-personal/business funding or actual handover date. confirmed_at is recorded confirmation time; actual_paid_date remains null unless an explicitly verified actual-date source field exists. Do not use invoice paid_at, attemptcreated_at or confirmation time as actual paid date. Existing Finance actual-date/qualified receipt or matched funding transaction/closed-period guards stay mandatory.

Hashes: invoice excludes ownrevision, settlement/payment excluded entirely; each payment and settlement hashes its exact fields excluding ownrevision, settlement includes orderedpaymentrevisions; row excludes revision ANDsettlement. Snapshot includesall. Payment-only changes update observed source facts without falsely changing invoice/RO revision or rewriting a bill if resolved cost is unchanged. A changed resolved expense requires reviewed cost correction. A claimed source attempt changing/reversing/disappearing requires payment review, preserving all EDG Finance/reserve/journal effects. Persist immutable source-observation evidence and latest observed state independently of accepted invoice/cost and reconciliation notes. Access loss hides current source facts while retaining booked audit history.

VerifiedRepairPayment adds optional source_attempt_id and source_attempt_revision, both or neither. A claim binds exact latest authorized confirmed attempt to this RO/customer/shop, rejects stale/nonconfirmed/reversed/refunded/unapplied facts, and verifies the whole **gross_received_amount**, equal to applied principal plus applied fee/tax (no split claim in this release). One active claim per tenant/shop/sourceattempt, concurrency protected; correction appends full Finance/reserve reversal and retains claim history before permitting a new claim. Source facts never bypass existing amount/date/funding/evidence verification. Manual Finance entry points must enforce the same optional-reference validation/projection rules. Refetch source before claiming so stale accepted observation cannot authorize a changed payment.

Public financial state adds source_settlement (latest authorized observation or null), source_payment_review_required boolean, source_payment_review_reasons[], alongside source_invoice_total and booked_cost. Existing invoice_total remains the booked/accepted cost. Optional source_claims display may list only same-link {source_attempt_id,source_attempt_revision,payment_id,reversed}. UI separates quote, settlement principal, actually charged fees, source confirmed/pending/remaining, actual received gross and EDG verified paid/due. Source payment method does not select EDG funding; recorded confirmation time never prefills actual payment date. Optional source-attempt linking preselects only the exact whole gross amount, with existing independent verification still required.

Source settlement/cash/confirmation/partial/refund/reversal hooks enqueue signed amount-free refetch wakeups with canonical settlement fingerprint in deduplication identity. Legacy invoice_changed wakeup kind may be reused; it does not mean a quote changed. No credentials or transport permissions are added. Focused tests must prove cash4886.38 case, full/partial/mixed card+cash, no-fee missing-settlement fallback, maximum-vs-earned fees, pending/failed, unknown dates/funding, inconsistent/refund/reversal/credits/tax review, independent payment hash updates, exact-once claims/concurrency/full reversal and no automatic payment or reserve projection. Independent Security/QA and existing browser/reconciliation/approval/release holds still apply.
