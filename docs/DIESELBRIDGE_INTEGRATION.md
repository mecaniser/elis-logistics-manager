# DieselBridge DB-094 invoice import

Elis consumes the read-only fleet invoice feed and stages invoices by authorized
business, DieselBridge shop and immutable invoice ID. Maintenance & Repairs now
has a DieselBridge panel for preview, paginated sync, invoice PDFs and explicit
repair-cost review. Newly added trucks qualify automatically through VIN matching.

## Configure and release

1. Release DieselBridge DB-094 and complete its required independent Security and
   QA gates before provisioning a read-only shop/bill-to credential. No historical
   bill-to mapping, production credential, or deployed API is assumed here.
2. Set `APP_AUTH_USERNAME`, the app's normal authentication secrets, and
   `APP_AUTH_TENANT_IDS` to the businesses the authenticated owner may access.
   These endpoints use the stronger `accounting_tenant` authorization: selecting
   `X-Tenant-ID` does not grant access. Local-only testing can use
   `ELIS_FINANCE_LOCAL_TENANTS` on loopback with no app username configured.
3. Set server `ELIS_DIESELBRIDGE_CONNECTIONS` to a JSON array, e.g.:

   ```json
   [{"slug":"repair-shop","tenant_id":1,"shop_id":"<DieselBridge shop UUID>","bill_to_id":"<explicit bill-to customer UUID>","base_url":"https://<DieselBridge host>","api_key_env":"DIESELBRIDGE_REPAIR_SHOP_KEY"}]
   ```

   Store the provisioned key separately in the named server secret. The client
   sends it only in `X-API-Key` to the configured HTTPS origin and follows no
   redirects. No key is stored in the database, browser, or API response. Base
   URLs must be HTTPS origins without userinfo, path, query or fragment.
   Connection settings are trusted deployment configuration, never client input.
   One shop/bill-to scope has one connection per Elis tenant. Scope/origin changes
   on an established connection are rejected; reconcile before provisioning a
   different connection. Key rotation uses the same scope and secret name.
4. Apply the normal startup migration. It creates only
   `dieselbridge_connections` and `dieselbridge_invoices`; it does not import or
   backfill invoices or modify existing repairs or accounting rows. Migration
   is additive and idempotent for SQLite and PostgreSQL.
5. In Maintenance & Repairs, select **Preview page** first. It fetches at most
   100 source items and saves no import or cursor state. Then **Sync invoices**
   and **Continue sync** until complete. Preview is one page, not a full-account
   reconciliation. Reconcile source totals and truck identities before accepting
   any costs. No scheduler or automatic expense posting is enabled.

## Sync and data behavior

- Each request durably applies one page and its next cursor in one transaction.
  The exclusive upper watermark stays fixed across pages. The stored completed
  watermark advances only on the last page. Later windows overlap by one day.
  Failures roll back both page data and cursor progress; retries are safe.
- DieselBridge's actual implementation requires both UTC `updated_since` and
  `updated_before` on the first request. Elis supplies both, validates every
  returned watermark, and uses the source's authenticated opaque cursor unchanged.
- Identity is unique `(tenant_id, source_system, shop_id, invoice_id)`. Old
  revisions are ignored, identical replays are no-ops, and conflicting data with
  the same revision stops the page. Access removal wins a revision tie. The
  removal event ID is retained. The invoice number is display data, not identity.
- A normalized nonempty VIN must uniquely match a **truck** in the authorized
  Elis tenant. Trim/collapse whitespace and uppercase for comparison. Missing,
  unmatched, duplicate, trailer and SUV VINs remain review items. Fix the truck
  directory before confirming the cost; matching is checked again on acceptance.
  A previously assigned invoice never silently moves to another truck.
- **Confirm repair expense** requires the current revision, explicit repair
  expense treatment and a review note. It creates at most one repair and preserves
  the accepted source JSON and review as immutable `FinanceEvidence`. This JSON is
  the document reference; the PDF remains a live, scope-checked source download.
  Carried odometer readings are preserved in source JSON, not written as a new
  odometer observation. The current implementation leaves the repair's miles
  unset; the source mileage and provenance remain available in staged JSON.
- Existing repairs with the same invoice number are held for reconciliation to
  avoid duplicating previously uploaded invoices. Linking an imported invoice to
  an existing repair is not automated in this version.
- Import and cost acceptance create **no** reserve withdrawal, journal entry,
  cash payment or finance event. A source `paid` status never confirms payment by
  Elis. Normal payment confirmation/accounting review remains a separate action.
- Revised accepted invoices, voids, cancellations, replacements and access removal
  flag explicit review. Accepted repair costs and posted entries remain intact.
  These flags appear in repair history, make old confirmations stale, and block
  new owner-payment posting until reconciled. Replacement invoices and their
  predecessors remain held even if the replacement arrives first. This version
  deliberately does not automate correction/reversal, rematching, or reacceptance
  of an existing repair. Corrections require explicit owner/accounting review.
- PDF requests authorize the Elis tenant and use the currently configured
  shop/bill-to key against the dedicated DB-094 PDF endpoint on every request.
  Removed access is denied locally; revocation is also enforced upstream. PDFs
  are never copied to public `/uploads` or redirected to staff PDF routes.

## Endpoints

All routes have prefix `/api/v1/accounting/dieselbridge`, require the normal
owner session and an authorized `X-Tenant-ID`, and return private/no-store data.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/connections` | Non-secret configured scopes and completed/pending sync state |
| POST | `/connections/{slug}/sync?dry_run=true` | Preview one page (default) |
| POST | `/connections/{slug}/sync?dry_run=false` | Commit one page; repeat while `has_more` |
| POST | `/connections/{slug}/sync?dry_run=false&restart=true` | Abandon an old cursor, replay from the last completed watermark (e.g. key rotation) |
| GET | `/invoices?after=0&limit=100&truck_id=...` | Tenant queue/history, optional tenant-checked truck filter, `next_after` pagination |
| GET | `/invoices/{id}/pdf` | Live scoped PDF download |
| POST | `/invoices/{id}/accept` | `{revision, cost_treatment:"repair_expense", note}` |

A changed/revoked credential cannot authorize a retained old cursor. After
rotation an owner can use `restart=true`; only a successfully saved page replaces
pending progress. Restart replays safely, never erases imported history. Reuse of
an invoice under another bill-to connection stops for reconciliation rather than
silently transferring it.

## Validation

`backend/tests/test_dieselbridge.py` exercises unique/duplicate/missing VINs,
additional trucks, trailer/SUV exclusion, tenant boundaries, unauthenticated
requests, stale acceptance, repeat acceptance, paid-status non-inference,
unchanged/old/new revisions, cancelled/void/replacement events, access removal,
manual-invoice collisions, pagination, overlap, interrupted-page rollback/replay,
key rotation, changed connection scope, malformed source pages, API-key and
redirect behavior, sanitized upstream errors, live PDF authorization, and
idempotent additive migration. Run alongside existing repair and finance tests:

```sh
cd backend
DATABASE_URL=sqlite:////tmp/elis-db094-test.db ../.venv/bin/python -m pytest tests -q
```

No live end-to-end connection has been tested. Activation still needs explicit
approval to provision the exact production shop/bill-to key and store it in the
EDG web service, followed by dry-run reconciliation against real invoices.

### Verified on 2026-10-30

- Targeted DB-094, repair history, payment confirmation and owner-posting suite:
  **64 passed**, including 36 new DB-094 cases.
- Full backend suite: **250 passed, 12 failed**. Untouched base `b727f7d`:
  **214 passed, the same 12 failed**. Eleven legacy repair/settlement tests omit
  the now-required tenant header; the remaining financed-trailer ROI assertion
  expects a zero break-even sale price while the implementation returns 645.
- Frontend production build passed; existing repair-review unit checks: **5 passed**.
- Playwright browser smoke with a synthetic local SQLite tenant: opened the
  invoice review form, accepted a $500 source-paid invoice and observed exactly
  one linked repair in Maintenance & Repairs. Database check confirmed
  `paid_from_reserve=false`, zero finance events, zero journal entries and zero
  reserve withdrawals.
- No live credentials, customer imports, deployment, or remote pushes performed.


### Production release verification (2026-10-30)

- Rebased the integration onto current deployed EDG main `bf0c9cf` so existing
  login, bank-monitor, accounting and investment features are preserved.
- Full backend suite: **530 passed, 2 optional PostgreSQL checks skipped**.
  Both optional checks were separately executed against disposable PostgreSQL 16:
  **2 passed** (additive migration/replay/acceptance; concurrent sync plus responsive
  unrelated ASGI heartbeat). Frontend production build and **57 frontend checks passed**.
- Independent security and QA reviews identified a blocking event-loop lock wait
  and a legacy repair-edit path that could invent reserve payment. Both were fixed
  and re-reviewed. Sync now runs as one worker-thread transaction; legacy edit and
  delete reject source-linked repairs before financial side effects. Three added
  tests cover title edits, truck remapping and deletion.
- Public production health checks passed for EDG and DieselBridge. The fleet export
  route returns 401 without credentials. Metadata-only Railway inspection confirmed
  no existing DieselBridge destination configuration; no raw environment values were
  retrieved. Three source Elis bill-to scopes exist. Only the Truck Pit Stop
  `Elis Logistics LLC (DBN)` scope currently has native finalized invoice snapshots
  (12); no existing active export key exists for any of the three scopes.
- Proposed activation is one read-only connection for EDG Elis Logistics tenant 1
  to that exact DBN bill-to scope. The other source bill-to records and historical
  mappings are not included. Persistent key creation and destination secret/config
  writes require action-time approval; no such action was performed during release
  preparation. No invoice, payment, mapping or accounting production data was changed.
