# Tenant bank detail privacy

Ordinary tenant list, detail, creation, and update responses return bank names,
account types, and `account_number_masked` / `routing_number_masked` only. Full
numbers and unknown properties in the stored bank JSON are excluded. Values
longer than four characters expose only their last four; short values are fully
masked. Reads do not modify stored numbers.

## Explicit access

`POST /api/tenants/{tenant_id}/bank-details` independently checks a valid session
for `APP_AUTH_USERNAME`, the existing server-side `APP_AUTH_TENANT_IDS` allowlist,
and an active business. It has no local-development authentication bypass.
The URL selects the business; the current switcher or an `X-Tenant-ID` header
cannot grant access to another business. Missing authorization fails closed.

Each request must also have `X-Bank-Details-Action` matching its `action`:

- Show or Copy: `{"action":"show","account_index":0,"field":"account_number"}`
  (or action `copy`, field `routing_number`). Returns only `{"value":"..."}`.
- Edit: `{"action":"edit"}`. Returns the selected business's full, explicitly
  typed `bank_accounts` for that editor only.

The action header is a browser request safeguard, not a substitute for session
and business authorization. All successful tenant responses and input-validation
errors use `Cache-Control: private, no-store`; access-denial errors also use it.
Validation errors omit submitted values so a failed ordinary write cannot echo
an account number.

## Browser lifetime and writes

The drawer fetches numbers only from Show, Copy, or Edit handlers. Both the drawer
and Businesses page fetch full accounts before opening an existing-business
editor. Full numbers never enter TenantContext, localStorage, or sessionStorage.
Hide removes the displayed value; closing, canceling, saving, or changing the
editor's business releases its sensitive component state. Pending reads are
aborted on close/unmount; late responses cannot reopen an editor or reveal a
number in another drawer. Copy fetches its field afresh and does not retain it
in component state. Clipboard writes begin during the click and can await the
authorized response.

Bank-number updates use the same session/business authorization. Omitting
`bank_accounts` preserves stored accounts; an explicit empty list clears them.
Masked summaries have different field names from write inputs, and submitted
mask characters or summary fields are rejected. No database migration is needed.

## Verification

On 2026-10-11:

- 35 focused backend privacy/account-security tests passed.
- Four frontend authentication-recovery tests passed.
- Frontend production build and lint of every changed frontend file passed.
- Chromium with a signed-in synthetic local database passed desktop and 390px
  browser flows: no automatic full-detail reads; field-scoped Show/Copy; Edit,
  Cancel, masked Save and preserved numbers; close/reopen; pending-read
  cancellation; editing a business different from the current switcher;
  unauthorized editing denied; no full numbers in browser storage.
- The browser Copy check inspected its Clipboard API payload through a test
  replacement, without writing synthetic bank details to the user's clipboard.
  Native Safari clipboard behavior was not verified.

Backend checks can be repeated with an isolated database:

```sh
DATABASE_URL=sqlite:////tmp/elis-bank-privacy-tests.db PYTHONPATH=backend \
  .venv/bin/python -m pytest backend/tests/test_tenant_bank_privacy.py backend/tests/test_auth_account.py -q
node --test frontend/tests/authRecovery.test.mjs
npm --prefix frontend run build
```

The frontend and backend contract must be released together. Deployment should
confirm the intended businesses are already in `APP_AUTH_TENANT_IDS`; do not
automatically widen that allowlist. This verification used synthetic data and
does not constitute production deployment or authenticated production verification.
