# Reviewed historical occurrence dates

A reconciliation note's date was previously reference-only. The financial importer used DBN `work_completed_at`, falling back to an evidenced invoice date. Consequently an owner-confirmed historical completion date in a note could disagree with the actual repair and expense date.

An explicit `date_treatment` on the existing append-only reconciliation endpoint now distinguishes:

- `note_only` (default, including all existing notes): reference evidence only.
- `confirmed_service_date`: use the reviewed `confirmed_service_date` for the proposed repair and expense.
- `source_default`: explicitly return to DBN completion date, then invoice date.

Both explicit treatments require `expected_source_revision` from a fresh authorized financial preview. The authenticated server supplies author and timestamp. The decision is scoped to tenant, connection, shop, customer and source RO. Corrections must supersede the latest explicit date decision; narrative notes cannot erase it. Source changes invalidate the decision until reviewed again. Payment-only observations do not change the RO revision and therefore do not invalidate an otherwise unchanged date decision.

The same resolver drives preview, creation, source-correction review and bill replacement. Preview digests bind the reviewed decision; immutable invoice evidence retains both the raw DBN source and the local decision. Later date changes on imported repairs require explicit source review. Active verified payments and closed accounting periods retain their existing correction blockers. Neither notes nor date review establish payment dates, funding or reserve withdrawals.

Migration `2026_10_31_dieselbridge_reviewed_dates` adds two columns without rewriting existing notes. Existing notes receive `note_only`; their old dates never become authoritative automatically. Existing note idempotency digests remain replay-compatible. The migration is additive/replay-safe on SQLite and PostgreSQL and keeps immutability guards intact.

## Equipment and temporary records

Equipment decisions can be prepared while financial activation is off. Authorized source access, exact current revision, tenant ownership, asset type, append-only correction and imported-repair reclassification protections remain required. Known trailer work cannot silently default to a tractor; an explicit trailer allocation keeps the source tractor identity separately for audit. No identities or production overrides are hardcoded into application code.

For reviewed temporary duplicates, use the existing exact-ID replacement preview/apply after the canonical repair exists. This is a separate reviewed operation, not an automatic title match. It archives the specified originals, preserves receipts and audit history, and reverses only verified prior effects once. Import replay does not recreate archived placeholders. Separate jobs must remain outside that explicit selection. Complete replacement and reconciliation before treating resulting metrics as final; the import and replacement are not one atomic operation.

## Release and historical application

This change does not grant historical invoice/PDF access, activate financial sync, alter production financial rows, or change cash-return formulas. After authorized release and any separately approved historical access, refresh the source preview, append the established owner-confirmed date/equipment decisions, refresh the full plan and verify dates/assets before import. Preserve original DBN/ETS evidence and differences in each repair's notes. Review exact temporary IDs and existing effects separately. Verify costs and actual payment/date/funding evidence before reserve posting.
