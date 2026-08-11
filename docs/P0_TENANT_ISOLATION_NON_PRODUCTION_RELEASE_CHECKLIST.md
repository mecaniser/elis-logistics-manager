# P0 Tenant-Isolation Non-Production Release Checklist

**Owner:** Release & Reliability

**Approvers:** QA Gatekeeper, Security & Identity, then Product & Delivery Lead

**Scope:** isolated staging verification of the P0 accounting tenant-authorization patch

**Production status:** prohibited. This checklist does not authorize a merge, production deploy, production data access, database mutation, Railway link, or Railway configuration change.

## Current gate status — candidate `cb77ce9`

**Recorded:** 2026-08-11

| Gate | Status | Evidence / remaining condition |
|---|---|---|
| Independent P0 tenant-isolation QA | **GO for `cb77ce9` only** | Auth-enabled focused suite `32/32`; auth-disabled focused suite `32/32`; canonical JSON `401` verified in a fresh process; 19 retained protected routes plus the separate reset tombstone; reset returns `410 ACCOUNT_RESET_UNAVAILABLE` with zero chart, journal-header, and journal-line changes |
| Security exact-candidate review | **PENDING** | Security & Identity is reviewing `cb77ce9`; no `APPROVED` verdict has been issued for this SHA at the time of this status update |
| Railway staging authorization | **NOT AUTHORIZED** | Requires Security `APPROVED` followed by explicit Product authorization naming the staging project/environment and immutable candidate SHA |
| Staging configuration/canary | **NOT RUN** | No Railway access has occurred; Sections 4–10 remain required after authorization |
| Broader backend suite | **NO-GO** | `87 passed, 12 failed`: 6 repair tests, 5 settlement tests, and 1 financed-trailer payoff test; failures are reported as unchanged baseline, not new P0 failures |
| Broader release / production | **NO-GO** | Focused P0 QA GO does not authorize merge, deploy, or production access |

The QA verdict is immutable-SHA scoped. Any code, test, configuration-default, dependency, or generated-artifact change after `cb77ce9` creates a new candidate and requires fresh QA and Security decisions.

### Minimum remaining non-production prerequisites

Before any Railway access or staging mutation:

1. Security & Identity must issue **APPROVED** for the exact `cb77ce9` candidate after dispositioning every open security-review item. A prior approval or review of another SHA does not carry forward.
2. Record the candidate's full 40-character commit hash and prove the staged build resolves to that immutable commit. The short SHA is not the final deployment identifier.
3. Product & Delivery must explicitly authorize access to named staging project, environment, application-service, and database-service IDs after Security approval. Production identifiers remain forbidden.

Before the P0 staging gate can become GO:

4. Complete the secret/allowlist preflight without printing values; staging authentication must be enabled, fail closed, and use only the approved synthetic Tenant A membership.
5. Prove staging database, domain, storage, logs, and outbound integrations are isolated from production.
6. Execute the two-tenant staging matrix, export isolation, denial parity, zero-side-effect, audit/log-redaction, readiness, and reset `410` checks in Sections 5–9 against the deployed full SHA.
7. Rehearse the Section 10 stop path. The known-vulnerable baseline is not an acceptable reachable rollback target; keep staging unavailable or roll forward to a Security-approved safe build.
8. QA and Security must reconfirm the staging evidence against the deployed SHA. The local focused-suite GO does not substitute for staging evidence.

Before the broader non-production release gate can become GO:

9. Resolve the 12 full-suite failures and obtain a green full backend suite. The 11 repair/settlement failures must be updated to the required tenant-context contract rather than weakening fail-closed runtime behavior; the financed-trailer payoff failure requires an independently verified expected-value/business-rule disposition.
10. Re-run the full backend suite and all P0 focused tests on the resulting new SHA, then obtain fresh QA and Security verdicts.

Until these conditions are met, the only open lane is local review and correction of the isolated candidate. Railway and production remain closed.

## 1. Hard authorization boundary

Do not link this worktree to Railway, inspect Railway variables, create or duplicate an environment, deploy, or change any Railway setting until all three conditions are recorded:

- [ ] QA Gatekeeper has issued **GO** for the isolated patch commit.
- [ ] Security & Identity has issued **APPROVED** for the same commit.
- [ ] Product & Delivery Lead has explicitly authorized Railway access for a named **staging** project/environment and the exact candidate SHA.

Authorization must identify:

```text
candidate_git_sha:
qa_verdict_and_evidence:
security_verdict_and_evidence:
product_authorization_reference:
railway_project_id:
staging_environment_id:
staging_application_service_id:
staging_database_service_id:
staging_domain:
operator:
observer:
authorization_time:
```

Project names, screenshots without IDs, prior approval, or silence are insufficient. If any identifier is missing or points to production, stop.

## 2. Frozen P0 contract

The staging candidate must preserve these decisions exactly:

| Case | Required result |
|---|---|
| Missing or blank `X-Tenant-ID` | `400 TENANT_CONTEXT_REQUIRED` |
| Malformed, non-integer, zero, or negative selector | `400 TENANT_CONTEXT_INVALID` |
| Missing, expired, malformed, or invalid session | `401 AUTHENTICATION_REQUIRED` |
| Valid session without required permission | `403 PERMISSION_DENIED` |
| Tenant absent, inactive, or outside server allowlist | `404 RESOURCE_NOT_FOUND` |
| Object absent or owned by another tenant | Byte-equivalent `404 RESOURCE_NOT_FOUND` |
| Authorized `DELETE /api/accounting/chart-of-accounts/reset` | `410 ACCOUNT_RESET_UNAVAILABLE`; zero row changes |

`X-Tenant-ID` is a required selector only. The verified session plus the server-owned allowlist is authority. No wildcard, default tenant, default-all-active-tenants behavior, browser-storage authority, or request-supplied role/permission is allowed.

## 3. Candidate and topology preflight

Before staging access:

- [ ] Worktree is clean except for approved evidence files.
- [ ] Candidate SHA equals the SHA approved by QA and Security.
- [ ] Candidate diff contains the expected authority, object-loader, route, and test changes only.
- [ ] Route introspection proves exactly 19 retained protected `/api/accounting` routes.
- [ ] All 19 routes have a read, write, or export `TenantAuthority` dependency.
- [ ] The five export routes are present and protected:
  - `/api/accounting/export/journal-entries`
  - `/api/accounting/export/general-ledger`
  - `/api/accounting/export/balance-sheet`
  - `/api/accounting/export/income-statement`
  - `/api/accounting/export/trial-balance`
- [ ] The legacy reset tombstone is outside the 19 retained protected-route count and returns `410 ACCOUNT_RESET_UNAVAILABLE` after tenant authority is established.
- [ ] The candidate adds no production schema/data migration. If any migration appears, stop and return it to Release/Security for a separate review.
- [ ] Staging has its own database, domain, storage, and outbound-integration configuration. No staging variable may reference production.
- [ ] Staging contains only approved synthetic or specifically authorized sanitized data.

## 4. Secret and allowlist preflight

### 4.1 Handling rules

- Never print, copy into chat/tickets, screenshot, hash for sharing, or log any secret value.
- Keep shell tracing disabled: `set +x`. Do not use `env`, `printenv`, `railway variables`, or debug dumps that output values.
- Record only `PRESENT`, `MISSING`, `VALID`, `INVALID`, `DISTINCT`, and non-sensitive counts.
- Do not put passwords, session cookies, database URLs, or API secrets in command arguments, filenames, test names, or assertions.
- Use a restricted temporary directory and `umask 077` for cookie jars and response artifacts. Delete them when evidence capture finishes.
- Treat `APP_AUTH_TENANT_IDS` as sensitive configuration even though it contains IDs.

### 4.2 Required configuration

Verify presence and policy without displaying values:

| Variable | Required staging assertion |
|---|---|
| `APP_AUTH_USERNAME` | Present and nonblank; never returned in denial payloads |
| `APP_AUTH_PASSWORD` | Present and nonblank; used only for login verification |
| `APP_AUTH_SECRET` | Present, nonblank, and distinct from `APP_AUTH_PASSWORD`; session signing must not rely on the password fallback |
| `APP_AUTH_TENANT_IDS` | Present; comma-separated unique positive integers; no wildcard; no blank token; exact approved membership count |
| `APP_AUTH_COOKIE_SECURE` | Exactly `true` for HTTPS staging |
| `APP_SESSION_DURATION_SECONDS` | Positive and within the Security-approved maximum |
| `DATABASE_URL` | Present; resolves only to the named staging database |
| `FRONTEND_URL` | Exact HTTPS staging origin; not production and not a wildcard |
| storage credentials | Present for the approved staging store; no production bucket/cloud/folder |

Use an offline presence/shape check after Product authorizes staging variable access. This prints no values:

```bash
set +x
python3 - <<'PY'
import os

required = (
    "APP_AUTH_USERNAME",
    "APP_AUTH_PASSWORD",
    "APP_AUTH_SECRET",
    "APP_AUTH_TENANT_IDS",
    "APP_AUTH_COOKIE_SECURE",
    "APP_SESSION_DURATION_SECONDS",
    "DATABASE_URL",
    "FRONTEND_URL",
)

for name in required:
    present = bool(os.getenv(name, "").strip())
    print(f"{name}: {'PRESENT' if present else 'MISSING'}")

raw_ids = os.getenv("APP_AUTH_TENANT_IDS", "")
tokens = [part.strip() for part in raw_ids.split(",")]
valid_ids = bool(tokens) and all(token.isdigit() and int(token) > 0 for token in tokens)
unique_ids = valid_ids and len(tokens) == len(set(tokens))
no_wildcard = "*" not in raw_ids
print(f"APP_AUTH_TENANT_IDS_SHAPE: {'VALID' if valid_ids and unique_ids and no_wildcard else 'INVALID'}")
print(f"APP_AUTH_TENANT_IDS_COUNT: {len(tokens) if valid_ids else 0}")
print(
    "APP_AUTH_SECRET_PASSWORD_RELATION: "
    + (
        "DISTINCT"
        if os.getenv("APP_AUTH_SECRET")
        and os.getenv("APP_AUTH_PASSWORD")
        and os.getenv("APP_AUTH_SECRET") != os.getenv("APP_AUTH_PASSWORD")
        else "INVALID"
    )
)
print(
    "APP_AUTH_COOKIE_SECURE_POLICY: "
    + ("VALID" if os.getenv("APP_AUTH_COOKIE_SECURE", "").lower() == "true" else "INVALID")
)
PY
```

Acceptance:

- [ ] Every required variable is `PRESENT`.
- [ ] Allowlist shape is `VALID`; count matches the approved staging membership count.
- [ ] Signing secret and password are `DISTINCT`.
- [ ] Cookie secure policy is `VALID`.
- [ ] A database identity query records only staging database name, user, host address, port, PostgreSQL version, and observation time. It does not print the URL or password.
- [ ] Every allowlisted ID maps to an active staging tenant, and no additional tenant is inferred. Record pass/fail and count only.
- [ ] Starting a disposable candidate process with missing, empty, wildcard, malformed, or nonexistent allowlist membership fails startup or makes every protected accounting request fail closed.
- [ ] Authentication cannot silently disable itself in the staging environment.

Any failed assertion is **NO-GO**. Do not “temporarily” broaden the allowlist to make a test pass.

## 5. Two-tenant staging fixture

Use two synthetic tenants with unmistakable, non-sensitive sentinels:

| Fixture | Tenant A, authorized | Tenant B, foreign |
|---|---|---|
| Tenant | active | active |
| Principal membership | explicit `{A}` only | not in Principal A allowlist |
| Truck | unique A sentinel | unique B sentinel |
| Parent/child accounts | unique A codes/names | unique B codes/names |
| Journal header/lines | unique A description/amount | unique B description/amount |
| Typed source references | A settlement and repair | B settlement and repair |
| Export rows | A-only values | B-only sentinel values |

Fixture rules:

- [ ] Tenant A and B IDs, names, codes, descriptions, amounts, and filenames are synthetic.
- [ ] B sentinels are easy to search in JSON, CSV, XLSX shared strings, PDF text, filenames, headers, logs, and audit events.
- [ ] Baseline row counts and canonical hashes are captured separately for tenants A and B.
- [ ] Baseline includes journal headers, journal lines, accounts, trucks, settlements, repairs, and any export/audit persistence.
- [ ] No staging scheduler, import, webhook, email, or external side effect can alter the fixture during the canary.

## 6. Canary execution order

Run in this order. Stop at the first disclosure, fail-open, or side effect.

### 6.1 Authentication precedence

- [ ] No session + no tenant header returns `401 AUTHENTICATION_REQUIRED`.
- [ ] Invalid/expired/tampered session + valid A header returns the same `401` body.
- [ ] Responses do not echo cookie content, username, tenant selector, or configuration state.

### 6.2 Missing and invalid selector

With a valid Principal A session, parameterize all 19 retained routes:

- [ ] Header absent: `400 TENANT_CONTEXT_REQUIRED`.
- [ ] Header blank/whitespace: `400 TENANT_CONTEXT_REQUIRED`.
- [ ] Header `abc`, decimal text, zero, and negative: `400 TENANT_CONTEXT_INVALID`.
- [ ] No route returns `200`, `422`, redirect, HTML application shell, or a streaming response for these cases.
- [ ] No report generator, export serializer, database flush/commit, storage write, or success audit event occurs.

### 6.3 Foreign tenant selection

With Principal A and `X-Tenant-ID: B`, parameterize all 19 routes:

- [ ] Every request returns `404 RESOURCE_NOT_FOUND` before business queries or mutation.
- [ ] Response body is byte-equivalent to nonexistent/inactive tenant denial.
- [ ] No B sentinel, requested ID, tenant name, account code/name, journal description, amount, EIN, filename, or row count appears.
- [ ] Write and export baselines are unchanged.

### 6.4 Foreign-object denial while A is selected

With Principal A and `X-Tenant-ID: A`:

- [ ] B chart-of-account detail returns `404 RESOURCE_NOT_FOUND` identical to a random nonexistent account.
- [ ] B journal-entry detail returns identical `404` and exposes no header, lines, accounts, source references, or amounts.
- [ ] B account general ledger returns identical `404`, not an empty `200`, and exposes no opening/closing balance.
- [ ] B `truck_id` on lists, reports, and exports returns `404`, not an empty result.
- [ ] Chart creation with B `truck_id` or B `parent_id` returns `404`; no account is created.
- [ ] Journal creation with B header truck, line truck, account, settlement reference, or repair reference returns `404`; no header or line is created.
- [ ] Unknown or unapproved `reference_type` cannot turn `reference_id` into an unscoped lookup.
- [ ] A corrupt cross-tenant journal-line/header fixture is excluded from screens, calculations, and exports and emits only approved integrity telemetry.

For every foreign-object case, compare status, stable code, message, content type, and body bytes with the equivalent nonexistent-object request. Do not claim non-enumeration based on status alone.

### 6.5 Authorized happy path

- [ ] Tenant A list, detail, ledger, report, write, and export canaries succeed only with the required permission.
- [ ] Responses and artifacts contain A sentinels and no B sentinel.
- [ ] A read-only principal receives `403 PERMISSION_DENIED` on writes; counts/hashes remain unchanged.
- [ ] A principal without `accounting.export` receives `403`; export generator is not invoked and no bytes/artifact are produced.
- [ ] Concurrent A-authorized and B-denied requests do not leak request context between tasks or connections.

### 6.6 Reset suppression

- [ ] Route introspection shows exactly 19 retained protected routes plus the separate legacy `DELETE /api/accounting/chart-of-accounts/reset` tombstone; reset is not counted as a retained route.
- [ ] With a valid session, authorized Tenant A selector, and any available role/permission set, reset returns `410 ACCOUNT_RESET_UNAVAILABLE` in the stable error envelope.
- [ ] Tenant authority runs before the tombstone response: authentication/context failures retain their frozen `401/400/404` behavior, while an authorized tenant context receives `410` without entering reset logic.
- [ ] No accounting-data query, delete, flush, commit, cache invalidation, file operation, or reinitialization occurs after tenant authority is established.
- [ ] Accounts, journal headers, journal lines, snapshots, closed-period history, sources, and packages remain byte/count/checksum equivalent to baseline.
- [ ] Repeating the reset request returns the same `410` response and leaves the same zero-change evidence.
- [ ] No role, including a fully permitted compatibility principal, can activate bulk deletion.

## 7. Export-isolation gate

Exercise every supported format for all five export routes.

| Route | Formats to exercise | Foreign filter/object case |
|---|---|---|
| journal entries | CSV, XLSX | B `truck_id` and B typed reference/filter where supported |
| general ledger | CSV, XLSX | B `account_id` |
| balance sheet | PDF, XLSX | B tenant selection |
| income statement | PDF, XLSX | B `truck_id` and B tenant selection |
| trial balance | CSV, XLSX, PDF | B `truck_id` and B tenant selection |

Denied-export assertions:

- [ ] Correct stable denial status/body; no streaming response.
- [ ] No `Content-Disposition`, attachment filename, tenant name, row count, or format-specific metadata.
- [ ] Response body contains no CSV/XLSX/PDF signature or payload bytes.
- [ ] Serializer/report-generator spies show zero invocation when authority or filters fail.
- [ ] No local, object-store, database, audit-success, or temporary export artifact remains.

Authorized-export assertions:

- [ ] Filename and internal title identify Tenant A only.
- [ ] CSV parsing returns only A rows.
- [ ] XLSX workbook, worksheets, cells, formulas, shared strings, metadata, and hidden content contain no B sentinel.
- [ ] PDF text and metadata contain no B sentinel.
- [ ] General-ledger opening balance, rows, and closing balance use tenant-qualified line, journal-header, and account predicates.
- [ ] Export totals equal the corresponding authorized on-screen/API report for the same boundary.
- [ ] Repeating the export under Principal A cannot reuse a cached Tenant B artifact.

Any foreign sentinel anywhere in an artifact is an immediate **NO-GO**, even if the visible first page/sheet is correct.

## 8. Audit and log-redaction gate

Capture a bounded staging log/audit window using request IDs. Restrict evidence access.

### Required audit evidence

- [ ] Authentication failure, missing/invalid context, permission denial, resource-not-found denial, authorized write, authorized export, and reset attempt produce the Security-approved event behavior.
- [ ] Events include timestamp, release SHA, route template, action, outcome, stable error class, request/correlation ID, and approved actor identifier.
- [ ] Authorized write/export events bind to the authorized tenant and resource without trusting request claims.
- [ ] Denied writes record no success event; denied exports record no export-success/artifact event.
- [ ] Resource-not-found events do not distinguish nonexistent, inactive, nonmember, or foreign ownership in externally visible fields.

### Forbidden in application, platform, and audit logs

- [ ] `APP_AUTH_PASSWORD`, `APP_AUTH_SECRET`, session cookie/token, `Authorization`, raw cookie headers, or login request body.
- [ ] `DATABASE_URL` or embedded database credentials.
- [ ] Raw `APP_AUTH_TENANT_IDS` or a dump of environment variables.
- [ ] Cloud/object-storage API secrets or signed URLs.
- [ ] Bank account/routing values, EIN, source document contents, export bytes, or full financial payloads.
- [ ] Foreign tenant name/ID, account name/code, journal description, amount, source ID, filename, or existence distinction on denial.
- [ ] Tracebacks or SQL parameter dumps containing request/header/financial values.

Search both exact synthetic sentinels and high-signal secret labels. A label may appear in a configuration-validation message, but its value must not. Manually inspect surrounding context for every match. Do not copy a matched secret into the release record.

Redaction acceptance:

- [ ] No secret or prohibited financial value appears in build, deploy, runtime, HTTP, audit, test, or browser-console logs.
- [ ] Structured fields are allowlisted; arbitrary request headers/bodies are not serialized.
- [ ] Error logging preserves request ID and safe code while suppressing confidential payloads.
- [ ] Audit records are append-only for the test window and access is limited to approved reviewers.

## 9. Readiness gate

Staging is ready for the P0 canary only when:

- [ ] Railway is on the explicitly authorized staging project/environment and exact approved SHA.
- [ ] Build and startup completed without secret/config dumps.
- [ ] Database identity is staging-only and connectivity succeeds.
- [ ] Authentication is enabled and the fail-closed allowlist validation passed.
- [ ] Route introspection reports 19 retained protected routes and the separate reset tombstone returns `410 ACCOUNT_RESET_UNAVAILABLE` with zero row changes.
- [ ] The staging fixture is stable and baseline hashes/counts are recorded.
- [ ] A database-aware readiness probe passes, or equivalent recorded checks prove process, database, candidate SHA, and authority configuration. `/api/health` alone is not readiness evidence.
- [ ] No migration ran and no production service/database/storage reference exists.
- [ ] Observers can access bounded application/HTTP/audit logs and know the rollback trigger.

Do not start the canary if logging is unavailable; a security boundary cannot be released blind.

## 10. Immediate stop and rollback conditions

Stop at once on any of these:

- any foreign tenant/object returns data, metadata, timing-independent existence detail, or artifact bytes;
- any retained route lacks the authority dependency;
- a missing/invalid selector returns `200`, `422`, or defaults a tenant;
- absent/invalid allowlist configuration fails open;
- a denied write changes any row/hash/count;
- a denied export invokes generation or leaves bytes/artifacts;
- reset returns anything other than the contracted `410 ACCOUNT_RESET_UNAVAILABLE` for an authorized tenant context, or changes any row/checksum;
- response parity fails between foreign and nonexistent resources;
- authentication, permission, or tenant context bleeds across concurrent requests;
- a secret, cookie, connection string, allowlist value, or prohibited financial field appears in logs;
- staging references any production resource;
- readiness or observability becomes unavailable.

Rollback procedure:

1. Stop canary traffic and disable public access to the staging service.
2. Preserve the request IDs, bounded redacted logs, response hashes, candidate SHA, configuration-validation statuses, and pre/post data hashes.
3. Do not retry with a broader allowlist or weaker denial behavior.
4. Because the previous application is known vulnerable, do **not** restore it to a publicly reachable staging service. Redeploy a previously Security-approved safe build or keep the service unavailable while Backend fixes forward.
5. Confirm the database and artifact baselines are unchanged. If the P0 remains migration-free, no database rollback should be necessary.
6. Return **NO-GO** with the exact failed canary and evidence to Backend, QA, Security, and Product.

Production release cannot proceed until a rollback target that preserves tenant isolation exists. “Rollback available” is false if the only target reintroduces the P0 disclosure.

## 11. Evidence packet and final decision

The staging packet must contain no secrets or raw financial data:

```text
candidate_sha:
qa_go_reference:
security_approved_reference:
product_staging_authorization_reference:
staging_project_environment_service_ids:
config_presence_and_policy_results:
allowlist_validity_and_count_only:
database_identity_without_url_or_password:
route_inventory_result:
canary_test_command_and_exit_status:
missing_invalid_header_matrix:
foreign_tenant_object_parity_hashes:
denied_write_pre_post_hashes:
export_format_matrix_and_sentinel_scan:
audit_log_redaction_result:
readiness_result:
rollback_rehearsal_result:
reset_410_and_zero_change_result:
open_findings:
final_go_no_go:
reviewers_and_timestamps:
```

Final result is **GO for further non-production review** only when every checkbox passes and QA plus Security reconfirm the evidence against the deployed staging SHA. It is not production authorization.

Any failure or unavailable evidence is **NO-GO**. Product & Delivery alone decides whether a later, separately approved production release process may begin.

## 12. Source contracts

- Security frozen contract: `SECURITY_P0_COMPATIBILITY_AUTHORITY_CONTRACT.md` in the Security & Identity worktree.
- Backend patch specification: `docs/security-accounting-backend-patch-set.md` in the Backend Integration worktree.
- Authoritative integrated reset contract: `docs/financial-reporting/api-contracts-v1.md` and `docs/financial-reporting/current-and-target-architecture-v1.md` in the Architecture/API worktree.
- General release controls: `docs/RELEASE_RELIABILITY_RUNBOOK.md`.
