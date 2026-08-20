# Financial Reporting API and Schema Contracts v1

Status: Proposed
Base path: `/api/v1/accounting`
Media type: `application/json`
Date format: ISO 8601 calendar date (`YYYY-MM-DD`)
Timestamp format: RFC 3339 UTC
Money format: decimal string plus ISO 4217 currency

These contracts define the first target version. Examples are normative for field names and types but do not imply implementation.

## Contract rules

- Every request sends exactly one valid `X-Tenant-ID` and authenticated user or service credentials. The server derives the principal and tenant allowlist; the header only selects one tenant from that server-derived allowlist.
- Mutation requests require `Idempotency-Key`. Reusing a key with different content returns `409 IDEMPOTENCY_KEY_REUSED`.
- All IDs introduced here are opaque UUID strings.
- Unknown request fields are rejected. Response consumers must ignore unknown response fields within the same major API version.
- Money uses a string matching `^-?[0-9]+\.[0-9]{2}$` for USD. Arithmetic never uses public JSON floats.
- Collections use cursor pagination unless the response is a fixed report payload.
- Every response includes `X-Request-ID`; errors repeat it as `trace_id`.
- Readiness is always one of `pass`, `block`, or `unknown`. `block` and `unknown` both fail closed for packages/exports.
- Report and drilldown reads are snapshot reads. They never advance source cutoffs or calculate against newer data.

## Mandatory tenant-authority invariant

Tenant authority is a precondition for every accounting, policy, period, posting/source, evidence, reconciliation, report, drilldown, eligibility, package, artifact, export, and retained legacy-adapter request. No route in this domain is public or tenant-optional.

The invariant is evaluated in this order:

1. Authentication derives the user or service principal. Client input cannot name or replace the principal.
2. The server derives the principal's tenant allowlist and action permissions from its authorization authority.
3. Exactly one `X-Tenant-ID` header selects the request tenant. The selector is never authority by itself.
4. Missing, non-integer, non-positive, duplicated/conflicting, or otherwise malformed selectors return `400 TENANT_CONTEXT_REQUIRED` or `400 TENANT_CONTEXT_INVALID`. No repository query, count, existence check, report cache lookup, or object resolution may run first.
5. A syntactically valid selected tenant that does not exist or is outside the principal's allowlist returns `404 RESOURCE_NOT_FOUND`. The response does not disclose whether the tenant exists.
6. Resource IDs are resolved with `WHERE tenant_id = selected_tenant_id AND id = resource_id` or an equivalent mandatory scope. An absent object and an object owned by another tenant both return the identical `404 RESOURCE_NOT_FOUND` envelope.
7. `403 PERMISSION_DENIED` is reserved for an action the principal lacks inside an already authorized selected tenant. It is not used to reveal foreign tenant or object existence.
8. Tenant IDs in request bodies, query parameters, path parameters, idempotency metadata, cached report state, or source payloads cannot select or widen scope. Request schemas reject a client-supplied tenant selector with `400 TENANT_CONTEXT_INVALID`. Response resources may echo the server-resolved tenant ID.

This invariant applies equally to browser sessions and service-to-service posting. A trusted service principal still needs a server-derived allowlist, a selector header, and permission for the requested action.

### Route-class enforcement matrix

| Contract class | Required enforcement |
|---|---|
| `/context`, policy, and period reads | Authenticate, select allowed tenant, then resolve entity/policy/period within that tenant. |
| Posting events and source/evidence records | Service/user permission plus selected tenant; source IDs, evidence IDs, and idempotency keys are tenant-bound. |
| Reconciliation status/checks | Scope and cached results must match selected tenant before counts or reason codes are returned. |
| Report runs, results, and drilldowns | Run and every joined journal/subledger/evidence object must match selected tenant and frozen snapshot. |
| Eligibility, packages, artifacts, and downloads | Every included run/artifact must match selected tenant; signed/download state is resolved only after authority. |
| Retained `/api/accounting` adapters | Same invariant as v1. Compatibility never preserves tenant-optional behavior. |

### Adversarial request examples

Missing context fails before the accounting handler runs:

```http
GET /api/v1/accounting/context HTTP/1.1
Cookie: session=<redacted>
```

```json
{
  "error": {
    "code": "TENANT_CONTEXT_REQUIRED",
    "message": "X-Tenant-ID is required.",
    "status": 400,
    "trace_id": "req_01K...",
    "field_errors": [{"field": "header.X-Tenant-ID", "code": "REQUIRED", "message": "Provide exactly one tenant selector."}],
    "meta": {}
  }
}
```

Malformed or client-conflicting selectors are also 400:

```http
GET /api/v1/accounting/report-runs/run_01K.../result HTTP/1.1
X-Tenant-ID: tenant-42
Cookie: session=<redacted>
```

```json
{
  "error": {
    "code": "TENANT_CONTEXT_INVALID",
    "message": "X-Tenant-ID must be one positive integer selector.",
    "status": 400,
    "trace_id": "req_01K...",
    "field_errors": [{"field": "header.X-Tenant-ID", "code": "INVALID", "message": "Expected one positive integer."}],
    "meta": {}
  }
}
```

An attacker selecting tenant `9999` outside the authenticated principal's allowlist receives the same 404 used for an unknown tenant:

```http
GET /api/v1/accounting/context HTTP/1.1
X-Tenant-ID: 9999
Cookie: session=<redacted>
```

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Resource not found.",
    "status": 404,
    "trace_id": "req_01K...",
    "field_errors": [],
    "meta": {}
  }
}
```

An authorized tenant `17` requesting an account, journal, run, evidence item, package, or artifact owned by tenant `42` receives that identical 404. The response must not identify the foreign tenant or object type:

```http
GET /api/v1/accounting/report-runs/run_owned_by_tenant_42/drilldown?line_code=cash HTTP/1.1
X-Tenant-ID: 17
Cookie: session=<redacted>
```

A principal authorized to view tenant `17` but not create packages receives 403 only after tenant authority succeeds:

```http
POST /api/v1/accounting/report-packages HTTP/1.1
X-Tenant-ID: 17
Cookie: session=<redacted>
Content-Type: application/json

{"purpose":"management","report_run_ids":["run_01K..."],"formats":["pdf"]}
```

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to perform this action.",
    "status": 403,
    "trace_id": "req_01K...",
    "field_errors": [],
    "meta": {"required_permission": "accounting.package.create"}
  }
}
```

### Required tenant-boundary contract tests

These tests are release gates, not optional route-level coverage:

| Case | Request | Required result |
|---|---|---|
| Missing selector | Account, journal, ledger, report, source, evidence, package, or artifact request without `X-Tenant-ID` | 400 `TENANT_CONTEXT_REQUIRED`; assert no domain query/cache/file lookup. |
| Invalid selector | `X-Tenant-ID: tenant-42`, zero/negative/overflow, or two conflicting header values | 400 `TENANT_CONTEXT_INVALID`; assert no domain query/cache/file lookup. |
| Body override | `X-Tenant-ID: 17` plus `tenant_id: 42` anywhere in a write/report/package body | 400 `TENANT_CONTEXT_INVALID`; assert no idempotency or resource lookup. |
| Foreign tenant | Principal allowlist `[17]` plus `X-Tenant-ID: 42` | 404 `RESOURCE_NOT_FOUND`, identical to unknown tenant `9999`. |
| Cross-tenant account | Tenant `17` requests account ID owned by tenant `42` | 404 generic; no account fields or existence signal. |
| Cross-tenant journal | Tenant `17` requests journal ID/reference owned by tenant `42` | 404 generic; no lines, descriptions, or existence signal. |
| Cross-tenant ledger | Tenant `17` requests general ledger using tenant `42` account ID | 404 generic; no opening balance, count, or entries. |
| Cross-tenant source/evidence | Tenant `17` requests source or evidence ID owned by tenant `42` | 404 generic; no metadata, checksum, or download lookup. |
| Cross-tenant report/drilldown | Tenant `17` requests tenant `42` run/result/line | 404 generic; no cached totals, scope, or joined IDs. |
| Cross-tenant package/artifact | Tenant `17` requests tenant `42` package, eligibility, artifact, or download | 404 generic; do not resolve signed URL/storage metadata. |
| In-tenant permission denial | Authorized tenant `17` viewer attempts posting, approval, reopen, package, or download action without its permission | 403 `PERMISSION_DENIED` after tenant resolution. |
| Retained legacy adapter | Repeat the preceding cases against every retained `/api/accounting` route | Same status/envelope and query-order behavior as v1. |
| Destructive reset | Authorized request to legacy reset route for tenant `17` | 410 `ACCOUNT_RESET_UNAVAILABLE`; row counts/checksums unchanged. |

Tests must use at least two populated tenants with deliberately overlapping-looking names, dates, account codes, and source references. This prevents false passes caused by empty foreign fixtures or globally unique-looking test data.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /context` | Resolve the `/accounting` workspace context, layers, policy decisions, source cutoff, period state, and tri-state readiness. |
| `GET /policies/settlement-template` | Resolve the one effective gross/net template for an entity, revenue stream, and earning date. |
| `GET /periods/{period_id}` | Read period status, lock version, approvals, and allowed actions. |
| `POST /posting-events` | Accept an immutable internal posting event. Service-to-service only. |
| `GET /posting-events/{event_id}` | Read posting outcome and journal revisions. |
| `GET /reconciliation/status` | Get current reconciliation summary for a proposed report scope. |
| `GET /reconciliation/checks` | Page through checks and exceptions for a scope or run. |
| `GET /evidence/{evidence_id}` | Read tenant-scoped source-evidence metadata. |
| `POST /report-runs` | Create a reproducible run for any v1 report type. |
| `GET /report-runs/{run_id}` | Read run state, snapshot metadata, and links. |
| `GET /report-runs/{run_id}/result` | Read the typed result after completion. |
| `GET /report-runs/{run_id}/drilldown` | Resolve a report line to snapshot journal, subledger, and evidence references. |
| `POST /report-runs/{run_id}/cancel` | Cancel a queued or running run. |
| `GET /report-runs/{run_id}/export-eligibility` | Read the persisted export gate decision. |
| `POST /report-packages` | Create an immutable package from completed report snapshots. |
| `GET /report-packages/{package_id}` | Read package manifest, readiness, versions, and authenticated artifact links. |

## Shared types

### Resolved report scope

```json
{
  "tenant_id": 17,
  "entity_ids": [],
  "asset_ids": [],
  "currency": "USD",
  "accounting_basis": "accrual",
  "reporting_layer": "book",
  "accounting_policy_version": "accounting-policy/2026-01"
}
```

Rules:

- The example is a response/resolved-run scope. Create requests omit `tenant_id`; the server injects it from the authorized `X-Tenant-ID` selector.
- An empty dimension list means all authorized records in the tenant.
- v1 is single-currency per run. Mixed-currency data returns `422 REPORT_CURRENCY_UNAVAILABLE` until translation policy exists.
- `accounting_basis` is `accrual` or `cash`. Unsupported basis/policy combinations return `422 ACCOUNTING_BASIS_UNAVAILABLE`.
- `reporting_layer` is `book`, `tax`, or `lender`. Tax and lender layers apply immutable adjustment/presentation sets to the same frozen authoritative book snapshot; they do not select alternate source ledgers.
- `accounting_policy_version` may be omitted on run creation to select the effective policy. The resolved value is always persisted and returned.

### Accounting workspace context

`GET /context?as_of_date=2026-07-31&reporting_layer=book`

```json
{
  "tenant_id": 17,
  "legal_entity_id": "entity_01K...",
  "reporting_layer": "book",
  "accounting_basis": "accrual",
  "period": {
    "period_id": "period_01K...",
    "start_date": "2026-07-01",
    "end_date": "2026-07-31",
    "status": "soft_closed",
    "lock_version": 3
  },
  "source_cutoff": {
    "recorded_through": "2026-08-11T19:42:00Z",
    "posting_event_watermark": 29118,
    "ledger_watermark": 18442,
    "source_manifest_version": "source-manifest.v1",
    "source_manifest_checksum": "sha256:...",
    "policy_versions": {
      "accounting": "accounting-policy/2026-01",
      "settlement_template": "settlement-template/gross-principal/3",
      "evidence": "evidence-policy/1",
      "layer_adjustments": null
    }
  },
  "readiness": {
    "state": "unknown",
    "reason_codes": ["RESERVE_OWNERSHIP_POLICY_UNKNOWN"],
    "blocking": true
  },
  "available_report_types": ["profit_and_loss", "balance_sheet"],
  "unavailable_report_types": [
    {"report_type": "cash_flow", "state": "block", "reason_codes": ["BANK_RECONCILIATION_INCOMPLETE"]}
  ]
}
```

The frontend must render `unknown` as an explicit unresolved state with reason text and remediation ownership. It must not treat an absent context, empty reason list, timeout, or unsupported layer as `pass`.

### Policy decision and evidence states

Policy decisions are `approved`, `rejected`, `pending`, or `unknown`. `pending` means an identified owner/evidence request exists; `unknown` means the required fact, owner, or evaluation coverage is not established. Neither state may be replaced by a default rule.

`GET /policies/settlement-template?legal_entity_id=entity_01K...&revenue_stream=carrier_settlement&effective_on=2026-07-31` returns exactly one approved template/version or `422 POLICY_DECISION_UNRESOLVED`. Overlap is an error, not “latest wins.” `GET /periods/{period_id}` returns `open`, `soft_closed`, `locked`, or `reopened`, the immutable `lock_version`, preparer/reviewer approvals, and allowed actions. These are read contracts for the reporting workspace; policy approval, closing, reopening, and adjusting-entry commands require separate role-controlled write contracts before implementation.

Source evidence verification is `unverified`, `verified`, `rejected`, `expired`, or `unknown`. `GET /evidence/{evidence_id}` returns metadata only:

```json
{
  "evidence_id": "evd_01K...",
  "evidence_version": 2,
  "tenant_id": 17,
  "legal_entity_id": "entity_01K...",
  "evidence_type": "carrier_settlement",
  "source_checksum": "sha256:...",
  "verification_state": "verified",
  "effective_period": {"start_date": "2026-07-28", "end_date": "2026-08-03"},
  "verified_at": "2026-08-05T14:12:00Z",
  "supersedes_evidence_version": 1
}
```

Evidence content uses a separate authenticated download action. A newer evidence version never changes a prior report's source cutoff or package manifest.

### Money and report line

```json
{
  "line_code": "operating_revenue",
  "label": "Operating revenue",
  "amount": "125000.00",
  "currency": "USD",
  "account_ids": ["acc_01K..."],
  "children": []
}
```

`line_code` is stable within a report schema version. Labels may change without breaking clients. Consumers must key logic on `line_code`, not labels or account names.

### Report metadata

Every result includes:

```json
{
  "run_id": "run_01K...",
  "report_type": "profit_and_loss",
  "report_schema_version": "financial-report.profit-and-loss.v1",
  "generated_at": "2026-08-11T19:45:00Z",
  "scope": {
    "tenant_id": 17,
    "entity_ids": [],
    "asset_ids": [],
    "currency": "USD",
    "accounting_basis": "accrual",
    "reporting_layer": "book",
    "accounting_policy_version": "accounting-policy/2026-01"
  },
  "ledger_watermark": 18442,
  "source_cutoff": {
    "recorded_through": "2026-08-11T19:42:00Z",
    "posting_event_watermark": 29118,
    "ledger_watermark": 18442,
    "source_manifest_version": "source-manifest.v1",
    "source_manifest_checksum": "sha256:...",
    "policy_versions": {
      "accounting": "accounting-policy/2026-01",
      "settlement_template": "settlement-template/gross-principal/3",
      "evidence": "evidence-policy/1",
      "layer_adjustments": null
    },
    "period_lock_version": 3
  },
  "readiness_state": "pass",
  "result_checksum": "sha256:..."
}
```

`source_cutoff` is immutable after a run starts. Every result, drilldown, eligibility decision, package manifest, and artifact repeats or references the same cutoff checksum.

## Posting event contract

`POST /posting-events`

```json
{
  "event_id": "evt_01K...",
  "event_type": "settlement.recognized",
  "event_version": 1,
  "source": {
    "source_type": "settlement",
    "source_id": "2841",
    "source_version": 6,
    "occurred_on": "2026-08-08",
    "recorded_at": "2026-08-11T19:40:12Z"
  },
  "posting_context": {
    "legal_entity_id": "entity_01K...",
    "settlement_template_id": "tmpl_01K...",
    "settlement_template_version": 3,
    "settlement_template_mode": "gross_principal",
    "accounting_policy_version": "accounting-policy/2026-01"
  },
  "evidence_refs": [
    {"evidence_id": "evd_01K...", "evidence_version": 2, "checksum": "sha256:..."}
  ],
  "currency": "USD",
  "payload": {
    "asset_id": "asset_01K...",
    "gross_revenue": "5250.00",
    "cash_received": "4010.00",
    "expense_components": [
      {"code": "fuel", "amount": "980.00"},
      {"code": "dispatch_fee", "amount": "260.00"}
    ]
  },
  "payload_checksum": "sha256:..."
}
```

The accepted event resource records the server-resolved tenant ID, but the request body cannot supply it. For example, `X-Tenant-ID: 17` plus a posting body containing `tenant_id: 42` returns `400 TENANT_CONTEXT_INVALID` before idempotency lookup or source resolution.

Accepted event types in v1:

- `settlement.recognized`
- `settlement.cash_received`
- `repair.incurred`
- `repair.paid`
- `asset.acquired`
- `asset.depreciation_recorded`
- `asset.disposed`
- `debt.opened`
- `debt.principal_paid`
- `debt.interest_incurred`
- `debt.adjusted`
- `manual_journal.requested`

An operational update emits a new `source_version`; it never overwrites an old event. The posting engine reverses the prior active effect when the new event supersedes it. `202 Accepted` returns the event resource. A duplicate event/payload returns the original resource; a duplicate identity with a different checksum returns `409 POSTING_EVENT_CONFLICT`.

Settlement templates are effective-dated and versioned. `settlement_template_mode` is `gross_principal` or `net_agent`. A posting event whose earning date has no single approved matching template is retained with `failed` status and `POLICY_DECISION_UNRESOLVED`; it is never routed by tenant name or silently posted through a default template.

Posting event status is `accepted`, `processing`, `posted`, `superseded`, `failed`, or `dead_lettered`. Only `posted` and `superseded` are terminal success states.

## Reconciliation contracts

### Status request

`GET /reconciliation/status?report_type=profit_and_loss&start_date=2026-01-01&end_date=2026-07-31&accounting_basis=accrual`

Optional filters are `run_id`, `report_type`, `start_date`, `end_date`, `as_of_date`, `entity_id`, `asset_id`, `accounting_basis`, and `accounting_policy_version`. Period reports use start/end; point-in-time reports use `as_of_date`. Mixing both forms returns `422 INVALID_REPORT_PERIOD`.

### Status response

```json
{
  "state": "block",
  "evaluated_at": "2026-08-11T19:43:22Z",
  "ledger_watermark": 18442,
  "scope_hash": "sha256:...",
  "counts": {
    "passed": 7,
    "warning": 1,
    "failed": 2,
    "unknown": 0,
    "running": 0
  },
  "blocking_check_codes": [
    "SOURCE_POSTING_MISSING",
    "DEBT_ROLL_FORWARD_MISMATCH"
  ],
  "checks_url": "/api/v1/reconciliation/checks?scope_hash=sha256%3A..."
}
```

The public readiness `state` is `pass`, `block`, or `unknown`. Check status is `passed`, `warning`, `failed`, `unknown`, or `running`; severity is `info`, `warning`, or `error`. Any required `failed` check produces `block`. Any required `unknown` or unevaluated check produces `unknown` unless a separate known failure already produces `block`. Both states set `blocking: true` for packages.

### Reconciliation check

```json
{
  "check_id": "chk_01K...",
  "check_code": "SOURCE_POSTING_MISSING",
  "check_version": 1,
  "status": "failed",
  "severity": "error",
  "dimension": {
    "source_type": "settlement",
    "source_id": "2841",
    "asset_id": "asset_01K..."
  },
  "expected": {"posting_count": "1"},
  "actual": {"posting_count": "0"},
  "variance": {"posting_count": "-1"},
  "message": "Settlement version 6 has no terminal posting.",
  "remediation_code": "RETRY_POSTING_EVENT",
  "first_observed_at": "2026-08-11T19:41:00Z",
  "last_observed_at": "2026-08-11T19:43:22Z"
}
```

Messages are for people. Automation uses `check_code`, `status`, `severity`, and `remediation_code`.

Required v1 blocking/unknown codes include `SUSPENSE_NOT_ZERO`, `SOURCE_EVIDENCE_MISSING`, `SOURCE_COVERAGE_UNKNOWN`, `POLICY_DECISION_UNRESOLVED`, `SETTLEMENT_TEMPLATE_MISSING`, `SETTLEMENT_TEMPLATE_OVERLAP`, `PERIOD_LOCK_CONFLICT`, `ENTITY_ELIGIBILITY_UNKNOWN`, and `ENTITY_INELIGIBLE` in addition to posting, roll-forward, trial-balance, and statement-equation checks.

## Report runs

### Create a run

`POST /report-runs`

```json
{
  "report_type": "profit_and_loss",
  "report_schema_version": "financial-report.profit-and-loss.v1",
  "scope": {
    "entity_ids": [],
    "asset_ids": [],
    "currency": "USD",
    "accounting_basis": "accrual",
    "reporting_layer": "book"
  },
  "period": {
    "start_date": "2026-01-01",
    "end_date": "2026-07-31"
  },
  "options": {
    "include_zero_lines": false,
    "comparison": null,
    "source_cutoff_mode": "capture_now"
  }
}
```

If that request instead includes `scope.tenant_id: 42` while `X-Tenant-ID: 17`, strict request validation returns `400 TENANT_CONTEXT_INVALID` before resolving entity, report, or source data. The body value is never ignored, honored, or used as a fallback.

`report_type` is one of:

- `profit_and_loss`
- `balance_sheet`
- `cash_flow`
- `debt_schedule`
- `asset_schedule`

P&L and cash flow require `period.start_date` and `period.end_date`. Balance sheet requires `period.as_of_date`. Debt and asset schedules accept either an as-of date or a period; period mode includes roll-forward activity.

`202 Accepted` returns:

```json
{
  "run_id": "run_01K...",
  "status": "queued",
  "report_type": "profit_and_loss",
  "request_hash": "sha256:...",
  "created_at": "2026-08-11T19:44:00Z",
  "status_url": "/api/v1/accounting/report-runs/run_01K..."
}
```

Run status is `queued`, `running`, `completed`, `failed`, or `cancelled`. Once execution starts, resolved scope, complete source cutoff, ledger watermark, policy/layer versions, period-lock version, and schema version are immutable. A caller may use `source_cutoff_mode: reuse` with a prior run ID to create cross-report statements from the exact same snapshot.

### Read a run

`GET /report-runs/{run_id}`

```json
{
  "run_id": "run_01K...",
  "status": "completed",
  "report_type": "profit_and_loss",
  "report_schema_version": "financial-report.profit-and-loss.v1",
  "accounting_policy_version": "accounting-policy/2026-01",
  "ledger_watermark": 18442,
  "readiness_state": "pass",
  "created_at": "2026-08-11T19:44:00Z",
  "started_at": "2026-08-11T19:44:01Z",
  "completed_at": "2026-08-11T19:44:02Z",
  "result_url": "/api/v1/accounting/report-runs/run_01K.../result",
  "export_eligibility_url": "/api/v1/accounting/report-runs/run_01K.../export-eligibility"
}
```

### Tenant-scoped drilldown

`GET /report-runs/{run_id}/drilldown?line_code=loans_payable&cursor=...`

```json
{
  "run_id": "run_01K...",
  "line_code": "loans_payable",
  "source_cutoff_checksum": "sha256:...",
  "items": [
    {
      "journal_line_id": "jline_01K...",
      "journal_revision_id": "jrev_01K...",
      "effective_date": "2026-07-18",
      "amount": "-1100.00",
      "currency": "USD",
      "subledger_ref": {"type": "debt_payment", "id": "dpay_01K...", "version": 2},
      "posting_event_ref": {"event_id": "evt_01K...", "event_version": 1},
      "evidence_refs": [
        {"evidence_id": "evd_01K...", "evidence_version": 1, "verification_state": "verified"}
      ]
    }
  ],
  "next_cursor": null
}
```

The server derives tenant and legal-entity scope from the authenticated run. It filters every journal, subledger, posting-event, and evidence join by that scope and by the run's source cutoff. Client-supplied tenant/resource scope cannot widen it. Out-of-tenant and post-cutoff resources return 404; response totals and timing must not reveal their existence.

## Report result schemas

### Profit and loss

Schema: `financial-report.profit-and-loss.v1`

```json
{
  "metadata": {"run_id": "run_01K...", "report_type": "profit_and_loss"},
  "period": {"start_date": "2026-01-01", "end_date": "2026-07-31"},
  "revenue": {
    "lines": [],
    "total": {"amount": "125000.00", "currency": "USD"}
  },
  "cost_of_revenue": {
    "lines": [],
    "total": {"amount": "73000.00", "currency": "USD"}
  },
  "gross_profit": {"amount": "52000.00", "currency": "USD"},
  "operating_expenses": {
    "lines": [],
    "total": {"amount": "21000.00", "currency": "USD"}
  },
  "operating_income": {"amount": "31000.00", "currency": "USD"},
  "other_income_expense": {
    "lines": [],
    "total": {"amount": "-4800.00", "currency": "USD"}
  },
  "net_income": {"amount": "26200.00", "currency": "USD"}
}
```

The full response uses the shared metadata object. The abbreviated metadata above is only to keep the example readable.

### Balance sheet

Schema: `financial-report.balance-sheet.v1`

```json
{
  "metadata": {"run_id": "run_01K...", "report_type": "balance_sheet"},
  "as_of_date": "2026-07-31",
  "assets": {
    "current": {"lines": [], "total": {"amount": "88000.00", "currency": "USD"}},
    "non_current": {"lines": [], "total": {"amount": "312000.00", "currency": "USD"}},
    "total": {"amount": "400000.00", "currency": "USD"}
  },
  "liabilities": {
    "current": {"lines": [], "total": {"amount": "46000.00", "currency": "USD"}},
    "non_current": {"lines": [], "total": {"amount": "174000.00", "currency": "USD"}},
    "total": {"amount": "220000.00", "currency": "USD"}
  },
  "equity": {
    "lines": [],
    "total": {"amount": "180000.00", "currency": "USD"}
  },
  "total_liabilities_and_equity": {"amount": "400000.00", "currency": "USD"},
  "balance_check": {"amount": "0.00", "currency": "USD", "status": "passed"}
}
```

### Cash flow

Schema: `financial-report.cash-flow.v1`. v1 uses the indirect method unless the policy explicitly selects another method.

```json
{
  "metadata": {"run_id": "run_01K...", "report_type": "cash_flow"},
  "period": {"start_date": "2026-01-01", "end_date": "2026-07-31"},
  "method": "indirect",
  "opening_cash": {"amount": "32000.00", "currency": "USD"},
  "operating_activities": {
    "net_income": {"amount": "26200.00", "currency": "USD"},
    "adjustments": [],
    "working_capital_changes": [],
    "net_cash": {"amount": "28400.00", "currency": "USD"}
  },
  "investing_activities": {"lines": [], "net_cash": {"amount": "-42000.00", "currency": "USD"}},
  "financing_activities": {"lines": [], "net_cash": {"amount": "30000.00", "currency": "USD"}},
  "net_change_in_cash": {"amount": "16400.00", "currency": "USD"},
  "closing_cash": {"amount": "48400.00", "currency": "USD"},
  "cash_roll_forward_check": {"amount": "0.00", "currency": "USD", "status": "passed"}
}
```

### Debt schedule

Schema: `financial-report.debt-schedule.v1`

```json
{
  "metadata": {"run_id": "run_01K...", "report_type": "debt_schedule"},
  "period": {"start_date": "2026-01-01", "end_date": "2026-07-31"},
  "instruments": [
    {
      "debt_id": "debt_01K...",
      "asset_id": "asset_01K...",
      "lender_name": "Example Lender",
      "status": "active",
      "interest_rate": "0.070000",
      "maturity_date": "2030-04-30",
      "opening_principal": {"amount": "92000.00", "currency": "USD"},
      "draws": {"amount": "0.00", "currency": "USD"},
      "principal_payments": {"amount": "11500.00", "currency": "USD"},
      "adjustments": {"amount": "0.00", "currency": "USD"},
      "closing_principal": {"amount": "80500.00", "currency": "USD"},
      "interest_expense": {"amount": "3570.00", "currency": "USD"},
      "current_portion": {"amount": "18000.00", "currency": "USD"},
      "long_term_portion": {"amount": "62500.00", "currency": "USD"},
      "roll_forward_check": {"amount": "0.00", "currency": "USD", "status": "passed"}
    }
  ],
  "totals": {
    "closing_principal": {"amount": "174000.00", "currency": "USD"},
    "interest_expense": {"amount": "7800.00", "currency": "USD"}
  }
}
```

Product forecasts such as profit-driven payoff dates are not accounting principal events. They may be shown in a separate analytics projection, not in this schedule.

### Asset schedule

Schema: `financial-report.asset-schedule.v1`

```json
{
  "metadata": {"run_id": "run_01K...", "report_type": "asset_schedule"},
  "period": {"start_date": "2026-01-01", "end_date": "2026-07-31"},
  "assets": [
    {
      "asset_id": "asset_01K...",
      "operational_vehicle_id": 44,
      "asset_class": "tractor",
      "placed_in_service_date": "2024-05-01",
      "depreciation_method": "macrs_5_half_year",
      "opening_cost": {"amount": "150000.00", "currency": "USD"},
      "additions": {"amount": "2500.00", "currency": "USD"},
      "disposals_at_cost": {"amount": "0.00", "currency": "USD"},
      "closing_cost": {"amount": "152500.00", "currency": "USD"},
      "opening_accumulated_depreciation": {"amount": "30000.00", "currency": "USD"},
      "depreciation_expense": {"amount": "24400.00", "currency": "USD"},
      "disposals_accumulated_depreciation": {"amount": "0.00", "currency": "USD"},
      "closing_accumulated_depreciation": {"amount": "54400.00", "currency": "USD"},
      "net_book_value": {"amount": "98100.00", "currency": "USD"},
      "roll_forward_check": {"amount": "0.00", "currency": "USD", "status": "passed"}
    }
  ],
  "totals": {
    "closing_cost": {"amount": "366400.00", "currency": "USD"},
    "closing_accumulated_depreciation": {"amount": "54400.00", "currency": "USD"},
    "net_book_value": {"amount": "312000.00", "currency": "USD"}
  }
}
```

## Immutable package and export gating

### Eligibility

`GET /report-runs/{run_id}/export-eligibility`

```json
{
  "decision_id": "elig_01K...",
  "run_id": "run_01K...",
  "eligible": false,
  "readiness_state": "block",
  "evaluated_at": "2026-08-11T19:44:03Z",
  "result_checksum": "sha256:...",
  "source_cutoff_checksum": "sha256:...",
  "reasons": [
    {
      "code": "RECONCILIATION_BLOCKED",
      "severity": "error",
      "message": "Two error-level checks failed.",
      "check_ids": ["chk_01K...", "chk_01M..."]
    }
  ]
}
```

The run is eligible only when:

- Status is `completed` and a result checksum exists.
- Reconciliation used the exact same source cutoff, ledger watermark, legal-entity scope, reporting layer, and result scope.
- Readiness is `pass`. `block`, `unknown`, and still-running evaluation all fail closed.
- Required suspense accounts are zero and required source evidence is verified at the snapshot cutoff.
- The accounting period and lock version permit the requested package purpose.
- The requested export format is supported by the report schema.
- The result has not been superseded or invalidated.
- Tax-organizer output has approved entity eligibility and tax mapping; lender output has an approved lender request profile and presentation layer.

Warnings do not block by default, but the policy may elevate specific warning codes. Eligibility is persisted and tied to the result checksum and source cutoff checksum.

### Create immutable package

`POST /report-packages`

```json
{
  "purpose": "management",
  "report_run_ids": ["run_01K...", "run_01M...", "run_01N..."],
  "formats": ["pdf", "xlsx"],
  "include_reconciliation_summary": true,
  "preparation_label": "management_prepared"
}
```

`purpose` is `management`, `tax_organizer`, or `lender`. All runs in one package must share tenant, legal entity, source cutoff checksum, reporting layer, basis, currency, and compatible policy versions. Supported v1 artifact formats are `pdf`, `xlsx`, and `csv`; allowed formats vary by report type and purpose. If any run is not `pass`, return `409 PACKAGE_BLOCKED` with every known and unknown eligibility reason in `error.meta`.

`202 Accepted` returns a package resource. The renderer reads persisted result payloads only; it cannot recalculate a report, resolve newer source versions, or advance the cutoff.

`GET /report-packages/{package_id}` returns:

```json
{
  "package_id": "pkg_01K...",
  "package_version": 1,
  "purpose": "management",
  "status": "ready",
  "readiness_state": "pass",
  "source_cutoff_checksum": "sha256:...",
  "manifest_checksum": "sha256:...",
  "manifest": {
    "report_runs": [
      {"run_id": "run_01K...", "report_type": "profit_and_loss", "result_checksum": "sha256:..."}
    ],
    "policy_versions": {},
    "period_lock_versions": [3]
  },
  "artifacts": [
    {
      "artifact_id": "art_01K...",
      "format": "pdf",
      "checksum": "sha256:...",
      "download_path": "/api/v1/accounting/report-packages/pkg_01K.../artifacts/art_01K.../download",
      "expires_at": "2026-08-18T19:44:03Z"
    }
  ]
}
```

Package status is `queued`, `rendering`, `ready`, `failed`, or `expired`; this lifecycle does not replace the separate readiness tri-state. A package version and manifest are immutable. Refreshing data or changing included reports creates a new package/version and new checksums. A ready artifact contains an authenticated API download path, never a storage-provider URL.

## Error semantics

All non-2xx JSON errors use:

```json
{
  "error": {
    "code": "INVALID_REPORT_PERIOD",
    "message": "start_date must be on or before end_date.",
    "status": 422,
    "trace_id": "req_01K...",
    "field_errors": [
      {"field": "period.start_date", "code": "DATE_AFTER_END_DATE", "message": "Must be on or before period.end_date."}
    ],
    "meta": {}
  }
}
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `TENANT_CONTEXT_REQUIRED` | `X-Tenant-ID` is missing. No accounting handler or repository lookup ran. |
| 400 | `TENANT_CONTEXT_INVALID` | Selector is malformed/conflicting, or request content attempts to select another tenant. |
| 400 | `MALFORMED_REQUEST` | Non-tenant JSON or parameter shape cannot be parsed. |
| 401 | `AUTHENTICATION_REQUIRED` | No valid session. |
| 403 | `PERMISSION_DENIED` | Principal lacks the requested action inside an authorized selected tenant. |
| 404 | `RESOURCE_NOT_FOUND` | Selected tenant is foreign/unknown, or object is absent/foreign. The envelope is identical. |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Same key, different request hash. |
| 409 | `POSTING_EVENT_CONFLICT` | Same event identity, different payload. |
| 409 | `REPORT_RUN_NOT_CANCELLABLE` | Run is already terminal. |
| 409 | `PACKAGE_BLOCKED` | One or more runs are `block`/`unknown`, mismatch snapshots, or fail purpose eligibility. |
| 409 | `PERIOD_LOCKED` | A mutation targets a locked accounting period. |
| 410 | `PACKAGE_EXPIRED` | Artifact retention elapsed. |
| 410 | `ACCOUNT_RESET_UNAVAILABLE` | Destructive chart/journal reset is permanently unavailable. No data changed. |
| 422 | `INVALID_REPORT_PERIOD` | Date form or ordering is invalid. |
| 422 | `ACCOUNTING_BASIS_UNAVAILABLE` | Requested basis is not supported by the policy/data. |
| 422 | `REPORT_CURRENCY_UNAVAILABLE` | Requested currency cannot be produced. |
| 422 | `REPORT_SCHEMA_UNSUPPORTED` | Schema version is unknown or retired. |
| 422 | `REPORTING_LAYER_UNAVAILABLE` | Tax or lender adjustment layer is not approved for the scope. |
| 422 | `ENTITY_ELIGIBILITY_UNRESOLVED` | Requested tax/lender purpose lacks an approved entity decision. |
| 422 | `POLICY_DECISION_UNRESOLVED` | Required gross/net, reserve, capitalization, debt, equity, or layer policy is pending/unknown. |
| 429 | `RATE_LIMITED` | Retry after the response header interval. |
| 500 | `REPORT_EXECUTION_FAILED` | Unexpected run failure; details stay out of the public message. |
| 503 | `POSTING_BACKLOG_UNAVAILABLE` | Posting/reconciliation dependency is unavailable. |

FastAPI validation errors must be translated to this envelope at the application boundary. Free-text `detail` responses are not part of v1.

## Compatibility and frontend governance

### Legacy adapters

During migration, these legacy routes may remain adapters only if the mandatory tenant-authority invariant wraps them before route logic:

| Legacy route | v1 mapping | Rule |
|---|---|---|
| Chart-of-account reads/writes | Tenant-scoped account service | Require selector and permission; object reads use selected tenant plus account ID. |
| Journal-entry reads/writes | Tenant-scoped posting/ledger service | Require selector and permission; object reads use selected tenant plus entry ID. |
| General ledger and trial balance | Tenant-scoped report run/drilldown | Account, entry lines, balances, caches, and exports stay in selected tenant. |
| `GET /api/accounting/income-statement` | Create/read `profit_and_loss` run | Preserve the current flat numeric response only in adapter code. |
| `GET /api/accounting/balance-sheet` | Create/read `balance_sheet` run | Preserve vehicle-named fields only in adapter code. |
| Direct report exports | Create v1 run, apply gate, create immutable package | Never bypass v1 eligibility or render from current data. |
| Tax-year summary and Schedule C | Future tax-organizer schemas | Schedule C readiness is `unknown` until eligibility is evaluated, `block` when ineligible/incomplete, and `pass` only after entity, method, mapping, adjustment, evidence, and approval gates. |
| `DELETE /api/accounting/chart-of-accounts/reset` | No replacement | Return `410 ACCOUNT_RESET_UNAVAILABLE`; never delete accounts, lines, entries, snapshots, or closed-period history. |

Legacy routes return `Deprecation`, `Sunset`, and `Link` headers once their v1 replacement is user-visible. A legacy field may not be added to v1 solely to preserve the old UI.

There are no tenant-optional exceptions for retained routes. If an adapter cannot enforce authentication, server-derived allowlist selection, object scoping, and action permission before all reads/writes, it is unavailable until repaired. Empty lists, aggregate zeroes, cache hits, file responses, redirects, and validation errors must not bypass tenant authority.

The current `GET /api/accounting/schedule-c` adapter must not be presented as filing-ready. Until the entity gate is implemented, its v1 workspace context is `unknown` with `ENTITY_ELIGIBILITY_UNRESOLVED`, package creation is disabled, and UI copy is “tax organizer draft.” If the approved entity classification is ineligible, the state becomes `block` with `ENTITY_INELIGIBLE`.

### Frontend workspace route aliases

The canonical frontend workspace is `/accounting`. Aliases preserve bookmarks but render the same workspace shell and context contract; they do not keep independent report implementations.

| Frontend path | Canonical workspace state |
|---|---|
| `/accounting` | Readiness overview with report context |
| `/accounting/reconciliation` | `/accounting?view=reconciliation` |
| `/accounting/reports` | `/accounting?view=reports` |
| `/accounting/reports/:runId` | `/accounting?view=report&run=:runId` |
| `/accounting/packages/:packageId` | `/accounting?view=package&package=:packageId` |
| `/accounting/income-statement` | `/accounting?view=new-report&type=profit_and_loss` |
| `/accounting/profit-and-loss` | `/accounting?view=new-report&type=profit_and_loss` |
| `/accounting/balance-sheet` | `/accounting?view=new-report&type=balance_sheet` |
| `/accounting/cash-flow` | `/accounting?view=new-report&type=cash_flow` |
| `/accounting/debt-schedule` | `/accounting?view=new-report&type=debt_schedule` |
| `/accounting/asset-schedule` | `/accounting?view=new-report&type=asset_schedule` |

Client-side navigation should replace aliases with the canonical URL after resolving them. The API remains canonical at `/api/v1/accounting`; legacy `/api/accounting` routes are compatibility adapters, not v1 aliases.

### Change policy

- Path major version changes only for breaking request/response or semantic changes.
- `report_schema_version` changes when report line meaning, required fields, or structure changes.
- `accounting_policy_version` changes when recognition, mapping, classification, depreciation, or materiality changes.
- Adding an optional response field is compatible. Removing/renaming a field, tightening accepted input, changing money sign semantics, or changing a line code is breaking.
- OpenAPI is the source of generated TypeScript types. Handwritten duplicate financial-report interfaces are prohibited after v1 adoption.
- CI must diff OpenAPI against the checked-in baseline and require Architecture & API Contracts approval for breaking changes.
- Backend contract tests validate examples and error envelopes. Frontend tests validate `pass`, `block`, and `unknown`; every run lifecycle state; snapshot mismatch; tenant-scoped drilldown denial; package blocking; and unknown additive fields.
- Every UI report displays period/as-of date, reporting layer, basis, policy/template versions, readiness state, source recorded-through cutoff, ledger watermark, and package snapshot status.
- `pass` enables eligible package actions. `block` shows known failures. `unknown` shows unresolved/unavailable evaluation. Only `pass` may enable export/package creation.

## Related

- [Current and target architecture](./current-and-target-architecture-v1.md)
- [ADRs, dependencies, and Product Lead handoff](./decisions-dependencies-handoff.md)
