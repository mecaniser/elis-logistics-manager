# DB-094 normal repair tiles and financial reconciliation

Status: **proposed local contract; execution blocked on reserve timing and individual historical attribution**. Architecture owner: financial_import_contract. Backend & Integrations is accountable for implementation. No production writes, historical grants, credentials, deployment or deletion are authorized by this document. Independent Security and QA gates remain required before financial release.

## Outcome and accepted policy

Each DBN repair order must produce one normal Maintenance & Repairs / Invoice review repair tile with source invoice evidence, correct truck, incurred date, cost and classification. It must participate in existing repair analytics and the approved repair-reserve calculation. The separate DBN history list becomes internal provenance/staging after successful migration; it must not cause a second visible expense.

The owner has accepted service-completion dates with evidenced invoice-date fallback, displaying recorded partial payments and balance due without inferring them from DBN status, negative reserve balances, recording invoices without assuming payment, replacing confirmed temporary truck 609 records with ETS-0386-97052, automatic processing of future newly finalized invoices, and review before applying subsequent invoice changes or cancellations. The owner has requested a guided, individual review of eight historical invoices; access has **not** been granted.

The precise reserve rule remains unresolved and must be a required input rather than an implementation default:

1. `reserve_recognition`: `invoice_incurred` or `confirmed_payment`. In the former, allocate the full net final invoice cost once; later partial/full payments do not withdraw the same amount again. In the latter, recognize the full expense once but withdraw only separately confirmed reserve-funded payment amounts, with each payment identified once. The statement that final invoices and partial payments come from reserve does not resolve which timing is intended. Never combine both methods for one obligation.
2. The expense-date rule is now resolved: `expense_date_rule = service_completion_else_invoice`. Use an evidenced service-completion date where present, otherwise an evidenced invoice date. Preserve the provenance and both source dates. Import/creation timestamps are not proven original invoice dates and cannot supply a fabricated fallback. If neither date is evidenced, return `DATE_EVIDENCE_REQUIRED`. Existing source completion dates prevent the four known regenerated invoice dates from moving expenses. `reserve_date_rule` remains tied to the unresolved reserve-recognition choice; payment-based withdrawals require the recorded payment date, while invoice-based reserve timing must be stated in the approved policy rather than inferred.

Partial-payment display must expose the explicitly recorded paid amount and remaining balance, with payment evidence/provenance. Never manufacture a partial amount or real-world balance from DBN `paid` status. With no confirmed payment facts, the UI must show unconfirmed/unknown payment information; a separately labelled EDG recorded obligation may still reflect the accepted invoice less its explicitly linked payments. Once a confirmed partial payment is recorded, remaining recorded balance is invoice amount less linked payments/credits exactly once.

Reserve timing and expense recognition are separate from proof of cash payment. The source workflow status `paid` is retained as source evidence; it does not by itself mark an EDG payment, credit Cash or create an owner reimbursement balance.

## Current evidence and integration traps

The read-only task audit recorded 58 normal repairs and 15 separate DBN history rows. Seven currently authorized finalized invoices total $8,069.64; eight current historical invoices remain outside the invoice/PDF grant. Current RO customer assignment proves operational association, not historical billed-customer attribution. The seven-invoice amount is not the full 15-order expense total.

Relevant existing code:

- `services/dieselbridge_repair_history.py` imports nonfinancial metadata only; it does not establish amount, invoice access or payment.
- `services/dieselbridge.py:accept` creates a normal `Repair` and `FinanceEvidence`, but does not create reserve withdrawals or journal entries. It currently chooses the regenerated invoice date and `maintenance` for every job; neither is suitable for this import contract without reviewed date/category selection.
- Generic `routers/repairs.py` create/update paths synchronize full-cost reserve withdrawals and invoke `create_repair_journal_entry`. The latter credits Cash, so the new importer must not call that path for an unpaid/unknown-payment invoice.
- `reserve_service.py` withdraws positive full repair cost dated on/after 2026-01-01. It does not implement partial-payment allocation and does not use `paid_from_reserve` to determine amount. Existing ledger entries support only positive `deposit`, `withdrawal`, `adjustment` types.
- Dashboard repair costs, individual repair chart, PM classification and operating metrics query normal repairs. Reserve balance and cumulative withdrawals query `repair_reserve_ledger`. All projections must exclude archived temporary repairs consistently. `maintenance` identifies PM; classify non-PM repairs correctly.
- Current legacy journals and the append-only FinanceEvent/Posting system are distinct report paths. Do not create the same expense twice within a book or infer cash by mirroring a legacy helper. The reviewed plan must identify which book receives which explicit posting and how report reconciliation links them.

## Identity, source authority and access

Use durable identity `(tenant_id, source_system='dieselbridge', shop_id, repair_order_id)`, never invoice number, title, date or regenerated invoice ID. Add a unique normal-repair source link containing canonical `repair_id`, accepted current invoice ID/revision, amount/date/category decision provenance, policy version and apply-operation ID. The existing operational history row may point to this link, but is not financial authorization.

The financial source contract must attest the **current finalized invoice for the RO**, not merely newest visible invoice date. Existing authorized invoice feed entries may supply current totals/evidence only when the source establishes that current relationship and there is exactly one eligible current invoice. Cancelled/voided/superseded versions are preserved as lineage, never added as separate costs. Missing inaccessible ancestors do not justify exposing their PDFs or charging them. An ambiguous current pointer is `CURRENT_INVOICE_REVIEW_REQUIRED`.

Operational metadata and authorized financial documents are joined only within the exact configured shop/customer and EDG tenant. Each VIN must uniquely match a same-tenant truck. An established source link cannot silently change truck/customer. Revocation, missing access, wrong scope, changed payload/hash or partial snapshots block financial apply and preserve the accepted cost pending review.

For each historical invoice, keep an individual attribution packet: invoice/RO IDs and numbers; source owner authorization check; immutable billed-customer snapshot and preserved invoice-document evidence if available; current RO customer association separately labelled; original and regenerated dates; gross/tax/discount/net totals and currency; mapping/evidence currently absent or present; exact proposed recipient customer/key scope; owner decision and evidence reference. Do not treat the current RO association alone as historical billing evidence. A source owner may inspect an invoice without authorizing its export to the customer key. Granting eight current documents does not grant all cancelled predecessors.

The source audit also reports that the existing historical-grant route rejects ETS-imported invoices/ROs and requires preserved invoice bytes, independent staff verification and an owner decision for eligible records. Preserve these gates. An ETS-origin packet is a **policy/contract incompatibility**, not a missing checkbox that the importer can bypass. Any source policy change must be separately designed, independently reviewed and explicitly authorized; neither current customer reassignment nor a broad owner approval silently removes those requirements.

## Proposed storage and reversible replacements

The exact migration is subject to implementation review, but it must provide:

1. The unique RO-to-normal-repair source link above.
2. An immutable import/reconciliation operation with canonical request digest, source snapshot/revision manifest, expected local-row digests, policy decisions, created links and all resulting projection/posting IDs.
3. A reversible archive/supersession record for each explicitly selected temporary repair: original repair ID, complete frozen record and evidence references, source/canonical repair link, original reserve/journal/finance links, reason, owner-reviewed mapping, operation ID and restore history. The repair and its attachments/evidence are retained. Normal active-repair query scope excludes archived records; archived records remain inspectable and cannot be edited/deleted through generic routes.
4. Append-only reserve correction links, including a distinct positive `withdrawal_reversal` classification with `reversal_of_id`. Cumulative **net withdrawals** are withdrawals less their linked reversals; manual adjustments remain manual adjustments. Balance is deposits plus adjustments minus net withdrawals. A compensating reversal must not inflate manual adjustments or erase the original withdrawal. Update constraints, serialization, totals, ledger UI, exports and tests together. Restoring a replacement appends the opposite linked correction once and cannot leave both duplicate expenses active.
5. A payment/reserve-allocation identity if `confirmed_payment` is selected. Each confirmed payment has source/evidence ID, amount, paid date, funding attribution and reserve-applied amount. Invoice cost and remaining liability are separate. Partial amounts cannot exceed the obligation unless an explicit credit/overpayment review handles it.

The strong temporary-component matches on truck 609 are ID123 (NOx/heating, 2026-03-21), ID125 (steer tires, 2026-03-27) and ID126 (batteries, 2026-04-18), each with null cost. Additional ID136 (cleaning, 2026-03-30, $150.00) and ID114 (diagnostic, 2026-02-26, $202.80) remain ambiguous and must be preserved until the owner confirms that specific job is covered by the ETS invoice. They are **not** an approved deletion/archive set. The earlier audit showed reserve withdrawals and legacy journals for 114/136, but no central FinanceEvent repair links (all 16 recorded events were settlements). Similar descriptions with different dates do not prove 114 is the same diagnostic event. Refresh exact rows and component mapping in the guided review. Use explicit `legacy_repair_ids`; never broad title matching or deletion by truck.

For an approved replacement, preview separately: removed active expense by original date/category; original reserve reversal by its date; new DBN expense by approved date; new reserve allocation according to policy; and bookkeeping reversal/replacement lines. Retain original journals and append approved bookkeeping corrections; do not call destructive legacy journal deletion. A prior Cash credit can be reversed as an identified bookkeeping correction without claiming a real bank refund. Payment-confirmation evidence must not transfer to a different invoice unless explicitly matched. Closed-period restrictions are reviewed, never bypassed.

## Proposed EDG API

All endpoints below are proposals under `/api/v1/accounting/dieselbridge/connections/{slug}/financial-import`. They require the existing strong accounting authentication, authorized tenant and owner-capable financial-write permission. Tenant comes from the authenticated dependency and is rechecked against server-managed connection configuration. Reject body-supplied tenant/shop/customer overrides. Cross-tenant/missing objects return the same 404 shape.

### Preview: `POST /preview`

No persistent writes or source grants. Request:

```json
{
  "version": "db094-financial-plan-v1",
  "repair_order_ids": ["source-ro-uuid"],
  "policy": {
    "version": "owner-policy-version",
    "reserve_recognition": null,
    "expense_date_rule": "service_completion_else_invoice",
    "reserve_date_rule": null,
    "allow_negative_reserve": true,
    "payment_inference": "none"
  },
  "decisions": [{
    "repair_order_id": "source-ro-uuid",
    "expected_invoice_id": "source-invoice-uuid",
    "expected_invoice_revision": "source-revision",
    "expense_date": null,
    "expense_date_basis": null,
    "category": null,
    "legacy_repair_ids": [],
    "legacy_component_evidence": [],
    "reserve_allocations": []
  }]
}
```

Null reserve-policy fields or missing date-evidence fields are valid only for preparing a **blocked** preview; they cannot produce an executable plan. Monetary fields use fixed two-decimal strings and source currency, with integer minor-unit arithmetic for sums; never floats. Category evidence distinguishes actual PM from other repairs. Explicit payment allocations require separate payment evidence and cannot derive from source `paid` alone.

Reply:

```json
{
  "version": "db094-financial-plan-v1",
  "executable": false,
  "plan_digest": "sha256-canonical-reviewed-plan",
  "source_manifest_digest": "sha256",
  "local_state_digest": "sha256",
  "policy_digest": "sha256",
  "rows": [{
    "repair_order_id": "source-ro-uuid",
    "action": "blocked",
    "canonical_repair_id": null,
    "invoice": null,
    "expense_before": "0.00",
    "expense_after": null,
    "replacement_ids": [],
    "expense_effective_date": null,
    "reserve_events": [],
    "posting_plan": [],
    "blockers": ["RESERVE_POLICY_REQUIRED"]
  }],
  "effects": {
    "active_repair_count_before": 58,
    "active_repair_count_after": null,
    "expense_delta_by_truck_month": [],
    "reserve_delta_by_truck_date": [],
    "resulting_reserve_balances": [],
    "payment_changes": [],
    "bookkeeping_corrections": []
  },
  "blockers": [],
  "warnings": []
}
```

Unavailable invoice access is represented by `invoice: null`, unknown amount/delta, and `HISTORICAL_ATTRIBUTION_REQUIRED`, never a fabricated zero. Do not report a final 15-order total until every selected current invoice is properly accessible and reconciled. Block the initial reviewed batch atomically unless the owner explicitly selects and approves a narrower subset.

Canonical digest: SHA256 of UTF-8 compact JSON with sorted keys and ASCII escaping, including version, exact scoped connection identity, RO/current-invoice manifests and hashes, per-row decisions, original repair/evidence/confirmation/reserve/posting digests, effective policy version, proposed operations and all period/truck deltas. Exclude volatile observation timestamps from the content digest; return them separately. Do not include secrets, bearer tokens, signed PDF URLs or private contacts in replies or hashes intended as public references.

### Apply: `POST /apply`

Requires explicit execution authorization, approved policy, all individual access grants and a reviewed executable preview. Proposed request:

```json
{
  "version": "db094-financial-plan-v1",
  "plan_digest": "reviewed-sha256",
  "source_manifest_digest": "sha256",
  "local_state_digest": "sha256",
  "policy_digest": "sha256",
  "decisions": []
}
```

Require an `Idempotency-Key` scoped to tenant + connection + action. Persist request digest with operation. Identical retry returns the original result; same key with different content returns 409 `IDEMPOTENCY_CONFLICT`. Proposed reply: `{operation_id, status:'applied'|'already_applied', plan_digest, created_repair_ids, archived_repair_ids, unchanged_repair_ids, reserve_event_ids, posting_ids, totals_before, totals_after}`. A normal retry creates no new repair, reserve movement, expense, posting, confirmation or payment.

Refetch/validate the source manifest, then acquire the existing tenant advisory transaction lock and lock affected local source/repair/reserve rows in deterministic order. Recompute the entire executable plan from supplied decisions and current local state. Compare all reviewed digests and source revisions before writes. Unique database constraints enforce RO identity and operation/event identities even with concurrent deliveries. On any stale input, authorization change, missing access or review requirement, rollback the complete operation. Do not fetch an unbounded PDF while holding the write lock; retrieve/hash authorized evidence first, then revalidate revisions before commit.

The source manifest must be a bounded consistent financial snapshot with current-invoice attestation and an observed watermark/revision, rather than an unverified join of independently changing operational and invoice reads. There is no distributed transaction across the two applications: acceptance records the exact observed immutable source revision. A source change after the final verified observation must arrive as a subsequent review event; never claim that the local commit freezes the source invoice. Failed/partial source reconciliation cannot advance the accepted manifest or infer absence.

New canonical repair, archival links, evidence references, reserve events, approved bookkeeping entries and operation result commit in one transaction. Injected failure after any step must rollback all projection/ledger effects. External event acknowledgement occurs only after durable inbox/operation receipt. The source financial payload is immutable evidence for the accepted revision; a later source change creates a review candidate, not in-place silent overwrites.

### Review and restoration

`POST /reviews/{id}/preview` and `/apply` use the same explicit decisions, digests, authorization, lock and idempotency rules for changed totals, cancellations, credits, truck identity changes and reversals. Accepted cost remains active with a review badge until approval. Hiding source text after revoked access does not silently erase a booked expense.

`POST /operations/{id}/restore/preview` and `/apply` create an explicit compensating plan. They retain the original operation/repair/evidence/postings; archive or reverse the replacement as necessary before reactivating approved originals. Restoration must not delete financial history, reopen closed periods implicitly, duplicate cash/payment facts or make two versions simultaneously active. This is a reviewed correction, not an unrestricted generic delete/undo endpoint.

Errors: 401 unauthenticated; 403 unauthorized tenant/financial action; 404 scoped object absent; 409 stale plan/source/local state, duplicate current invoice, identity conflict, closed period or idempotency conflict; 422 invalid/missing required execution policy/decision; 502 invalid/incomplete source protocol. Errors never expose credential values or cross-tenant existence.

## Immediate future finalization flow

There is currently no automatic finalization webhook or financial scheduler. To satisfy immediate future import, propose a durable source outbox event on successful invoice finalization and an authenticated EDG inbox/worker. Event contains only scoped IDs, immutable event ID, source revision, action and timestamp; EDG refetches authorized financial data through the existing read-only customer key. The event is a wake-up, not financial truth or customer-attribution proof.

Transport must have an independently scoped signing/verification mechanism, replay/time-window protection, durable delivery retries and backoff. Any new persistent secret or broader access requires its own action-time approval; none is created by this contract. Do not reuse an existing read-only API key as an invented webhook signing secret. Source outbox records customer scope at finalization; receipt rejects altered shop/customer/connection identity. Worker is connection/tenant serialized, with dead-letter review and reconciliation for missed events.

Only previously unseen RO/current-final-invoice identities with an approved automatic policy and complete evidence can create normal tiles and calculate their approved reserve/expense effects automatically. Unknown reserve policy or missing date evidence, duplicate candidates, missing history attribution or invalid currency blocks execution. Revisions, replacements and cancellations affecting an already booked RO create review items and preserve accepted amounts until approved. Repeated events, reordered deliveries and lost acknowledgements are harmless by operation/source identities. Operational metadata sync alone never triggers an expense.

## Acceptance and release gates

1. Exactly one active normal tile per selected RO; 603/609 assignments remain 6/9 before any approved overlap archive; original attachments/evidence remain inspectable. Canonical RO links survive regenerated invoice IDs.
2. All 15 selected current invoices accessible through approved scope or initial batch remains blocked. Missing totals are unknown, never zero; cancelled versions are not costs. Wrong tenant/customer/truck or revoked grants cannot apply.
3. A blocked preview with unset reserve policy writes nothing. The approved expense rule chooses service completion, then evidenced invoice date; missing both blocks apply. Import/created timestamps never become fabricated original invoice dates. Invoice service/issue/payment dates are separately preserved. Four known regenerated dates do not replace available completion dates.
4. Full-invoice policy withdraws once and subsequent partial payment does not withdraw again. Confirmed-payment policy books full expense once and applies each approved partial reserve allocation once. Negative balances are allowed and visible, never clamped.
5. Null/zero/no-charge temporary records cause no invented expense or withdrawal. Positive archived amounts are explicitly reversed once, with original journal/reserve records preserved. Candidate ID114 is not included just because its text says diagnostic. Failure and restoration tests prove reversibility.
6. New invoices recorded unpaid/unknown never create a cash credit, real payment, owner reimbursement or payment confirmation. Existing confirmations are preserved and matched explicitly. Book/report totals reconcile without duplicating the same expense.
7. Normal tile list, invoice review coverage, individual repair chart, per-truck/month/year totals, all-in cost per mile, PM timing, reserve ledger/net withdrawals/balance and exports all use the same active-record definition. Trailer costs and unrelated repairs remain unchanged. Monthly/yearly operating profit and settlement take-home definitions are reconciled explicitly rather than double-subtracting reserve contributions and repairs.
8. Identical replay and concurrent same-RO events create zero duplicate rows/withdrawals/postings. Changed source/local decisions stale the preview. Transaction failures leave originals active and all financial projections unchanged.
9. Updated/cancelled invoices leave accepted cost intact with review state until an approved correction. Invoice/PDF access removal preserves financial audit while withholding inaccessible cached source content.
10. Webhook tampering, replay, wrong scope, missing credentials, worker crash after commit and duplicate delivery tests pass. A finalized new invoice becomes a tile promptly only after policy/transport approval; revisions require review.
11. Local implementation/TDD and independent Architecture/Security/QA checks precede focused PRs. Production deployment, historical grants, initial financial apply and signed-in desktop/mobile acceptance require their specific remaining approvals/evidence. Prepare a read-only per-row before/after plan first. Do not mark this item Done while any reserve timing, date evidence, attribution, gate, release or runtime acceptance remains pending.


## Local preparation evidence

A pure preview builder (`backend/app/services/dieselbridge_financial_plan.py`) is prepared with no database/network/apply path and execution hard-disabled. TDD: missing-module RED then18 focused tests GREEN. It requires explicit reserve timing/date, preserves unconfirmed payment status, displays confirmed partial paid/due amounts, selects completion then evidenced invoice date, blocks owner-review-only source totals and unconfirmed cost assets/replacements, nets existing effects and reviews invoice changes/cancellations. It is not the full financial mutation/UI/worker implementation.

Owner-scoped read-only inspection subsequently establishes eight historical gross totals11,810.06 and all15 gross19,879.70 before reconciliation. All8 still lack attribution evidence/mapping; no grant approved. INV000023 lists six trailer tires and needs cost-asset confirmation. INV000006 lacks an immutable line snapshot. ETSINV0718 remains blocked by the imported-ETS historical-attribution guard.

The exact609 effects audit finds strong temporary components123/125/126, all currently null-cost with zero reserve/journal effects. Preserve cleaning136($150; withdrawal73/journal514), because its charge is absent from the invoice snapshot despite RO description. Preserve diagnostic114($202.80; withdrawal33/journal395), with independent invoice4076 evidence and business-Zelle paid confirmation. Do not net352.80 without contrary duplicate proof.
