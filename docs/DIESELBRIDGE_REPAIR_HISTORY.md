# DieselBridge repair-order history

Maintenance & Repairs and each truck detail page show separate DBN service-history
records. One source RO remains one entry through invoice replacements. Syncing
history never creates or updates a legacy repair cost, payment, reserve withdrawal,
finance event or journal entry.

The existing approved shop/customer connection calls
`GET /api/v1/fleet-invoice-exports/repair-orders`. This is a complete nonfinancial
snapshot, capped at 1,000 rows and rejected if oversized. It exports completed,
invoiced or paid ROs for that exact customer's operational history with same-shop
vehicles, excluding internal, deleted and cancelled ROs. No invoice references,
money, PDFs, contacts or private notes are included. Historical invoice/PDF
restrictions remain intact. Current RO assignment never backfills invoice bill-to.

Source contract: `truck-pit-stop/docs/contracts/db094-elis-repair-history.md`.
Canonical SHA256 uses sorted compact JSON, ASCII escaping and UTF-8. Item revision
excludes itself; snapshot digest covers version/shop/customer/items. The consumer
rejects partial snapshots, wrong scope/version/count, duplicate IDs, unknown
fields, wrong hashes, disallowed status and inconsistent date provenance before
writing any history.

Storage is additive: `dieselbridge_repair_history` and
`dieselbridge_history_sync`. Unique tenant/source/shop/RO identity prevents replay
duplicates. Source fetch, validation, writes and progress run atomically under the
tenant lock on a worker thread. Missing rows remain unavailable for review and
cached work text is withheld. VIN changes cannot silently move original links.

Service dates use completion timestamps, with explicit created-date fallback when
completion is missing. Regenerated invoice dates are not used. Existing repairs
on the same truck/date are annotated as review candidates, never merged or charged.

Authenticated routes under `/api/v1/accounting/dieselbridge`:

- `GET /repair-history?truck_id=...&after=0&limit=100` lists scoped history.
- `POST /connections/{slug}/repair-history/sync?dry_run=true` previews without writes.
- The same POST with `dry_run=false` saves the full snapshot idempotently.

The main panel offers preview/sync; truck pages show that truck only. Source
workflow status `paid` does not establish an Elis payment.

Validation:26 focused history cases;61 frontend tests and production build;39 source
history/invoice/historical tests;3 disposable PostgreSQL checks including concurrent
15-row imports with6/9 linking; synthetic browser preview/import/replay and both
truck pages. Independent Security and QA GO. Source/consumer publication/deployment
and authorized live15-row receipt remain pending external release approval.
