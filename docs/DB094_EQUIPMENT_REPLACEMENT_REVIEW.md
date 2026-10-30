# Equipment attribution and temporary repair replacement

Local release candidate, 2026-10-30. No publication, deployment, activation, historical grant, source correction or production financial mutation is authorized by this document.

## Equipment model

EDG already represents trucks and trailers in `trucks.vehicle_type`; each repair and reserve entry references that equipment's stable ID. Reuse those records and existing equipment pages/ROI/report filters. DBN's current v2 manifest already carries source vehicle ID and VIN. No DBN schema, export-version or credential expansion is needed for this focused implementation.

The financial importer now uniquely matches a normalized VIN across truck and trailer records. Duplicate VINs across either type require review. A whole-invoice equipment decision can explicitly select existing equipment before import. It preserves source vehicle/VIN separately from the cost asset, author, reason, time and correction chain. Trailer work can explicitly remain under a truck unit as an interim assignment when trailer identity is unknown. The tile retains that it was trailer work and that the assignment is interim. No trailer identity is inferred from unit number, tow pairing or description.

Equipment decisions cannot grant invoice access, establish a payment, change source service dates or move reserve money. Changing a source vehicle/VIN invalidates its decision. An imported cost cannot be silently reassigned: it requires a separately reviewed financial reclassification. Mixed-equipment invoices must be reconciled before whole-invoice assignment; splitting invoice amounts is outside this release.

Append-only `dbn_equipment_allocations` installs through an independent, replay-safe migration with ORM and SQLite/PostgreSQL update/delete guards. No existing repair, asset or financial row is rewritten. Existing seven eligible source invoices keep their current allocation until reviewed. The owner's instruction to book invoice 000023's trailer tires to unit609 is preserved in the private reconciliation decisions; it has not been applied in production, and its ETS match/date remain unresolved.

## Review endpoints

All paths below are relative to `/api/v1/accounting/dieselbridge`, use authenticated server-resolved tenant scope, and reject extra body fields. Mutations require `Idempotency-Key` and existing financial enablement. Preview routes do not commit.

- GET `/equipment-options`: this tenant's truck/trailer IDs, names, types and VINs.
- POST `/connections/{slug}/repair-orders/{ro}/equipment-allocation`: `asset_id`, `expected_source_revision`, `work_equipment_type`, explicit `interim_unit_allocation`, `reason`, optional prior `supersedes_id`. Corrections append; imported targets are blocked.
- GET `/repairs/{repair_id}/replacement-candidates`: active unmanaged same-equipment records; no title-based job match.
- POST `/connections/{slug}/financial-import/archive-preview`: `repair_order_id`, explicit unique `legacy_repair_ids`, `correction_date`. Requires an already accepted, active source target and a fresh unchanged authorized source manifest. Returns complete old repair/evidence references, existing withdrawals and journals, proposed cost removal/reserve correction, and digest.
- POST `/connections/{slug}/financial-import/archive-apply`: preview fields plus `expected_plan_digest`, `confirmed_same_job`, `reviewed_existing_effects`, `reason`. One transaction archives selected records, links to the canonical target, retains all original fields/attachments, appends exact inverse journal lines and reserve reversals only for verified existing entries, and records actor/time/snapshots. It never creates a payment or refund.
- GET `/connections/{slug}/financial-import/replacements/{operation_id}`: tenant/connection-scoped persistent audit.
- POST `/connections/{slug}/financial-import/replacements/{operation_id}/restore-preview`: `correction_date`.
- POST `/connections/{slug}/financial-import/replacements/{operation_id}/restore`: date, fresh `expected_plan_digest`, `reviewed_existing_effects`, `reason`. Preserves original archive audit, appends compensating reinstatement entries, and restores original record visibility. The source repair remains active: undo explicitly returns the pre-replacement state and can reintroduce duplicate expenses. UI warns before confirmation.

The normal repair tile provides both replacement and undo review controls. Selected IDs/date changes invalidate a preview; unchanged retries retain their key. Restored records retain their audit marker and cannot be edited/deleted or used for new claims through legacy flows. A second replacement of a restored record requires a separate review, rather than reusing already reversed original effects.

## Financial boundaries

Legacy reserve flags and null costs produce no inferred entries. Existing Finance claims/payments require a separate dependent-effect review and block this workflow. Cross-tenant/asset, already-corrected, managed, stale, unbalanced or inconsistent effects are rejected. Correction dates cannot precede affected original dates or be in the future. Undated repairs with financial effects require reconciliation; closed original/correction periods block execution. Restore revalidates original and compensating snapshots and cannot precede replacement.

Apply/restore, normal legacy repair edits/deletes/image removal, Finance commands, and manual journal writes share the tenant lock. Manual journals cannot forge DBN-managed references or append to reviewed replacement records. A PostgreSQL edit-versus-replacement test confirms a prior edit commits first, invalidates the preview, and creates no archive/reversal.

The temporary609 candidate evidence identifies records123/125/126 with null costs/no withdrawals and record136 with an existing150.00 withdrawal/journal. Record114 is a separate202.80 repair and is not automatically selected. No production selection or replacement has executed; historical target ETS-0386-97052 remains access-blocked.

## Verification and release holds

Complete backend:758passed, no skips, disposable PostgreSQL enabled. Frontend:92passed; TypeScript/Vite build and changed-file ESLint pass. Independent read-only review found no remaining actionable blocker after concurrency, restoration protection and chronology fixes.

Synthetic browser: explicit trailer selection saved without importing or moving reserves; import produced5truck603/9truck609/1trailer tiles, with source identity preserved; repeat preview15unchanged. Synthetic temporary150.00 duplicate archive retained original rows and appended one matching reserve/journal reversal with no payment. Browser undo evidence is recorded separately in the task receipt.

Production read-only preview after the previous merged release:15ROs, seven create candidates, eight blocked by historical attribution; no batch executed. Financial API/worker/source delivery flags remain off. This new candidate must be reviewed, published and released through the approved process before use. Historical attribution/date/amount/asset decisions and verified payment dates/funding remain separate holds.
