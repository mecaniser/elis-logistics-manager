# Financial Reporting Release and Reliability Runbook

**Owner:** Release & Reliability

**Approver / handoff:** Product & Delivery Lead

**Scope:** Railway application service, Railway PostgreSQL, financial-reporting migrations, report-version and period-lock behavior

**Runbook status:** Drafted from repository evidence on 2026-08-11; live Railway topology is **not verified** because this checkout is not linked to a Railway project
**Current release decision:** **NO-GO for a production financial-reporting rebuild** until the blocking controls in this document are implemented and the live topology evidence is captured

This is an operational control document. It does not authorize a deployment, production mutation, merge, restore, or DNS/database cutover. Every approval gate requires an explicit written decision from the named approver.

## 1. Executive audit

| Area | Repository evidence | Assessment | Required disposition |
|---|---|---|---|
| Deployment source | `railway.json` contains restart policy only. `Dockerfile` builds React and starts `backend/start.sh`; the script starts one Uvicorn process. Historic docs describe Nixpacks/start-command behavior that is no longer present in `railway.json`. | **At risk:** repository docs and effective container topology disagree. Live Railway builder, root directory, branch, region, replicas, domains, and auto-deploy settings are unknown. | Capture the live configuration in the release record and treat the Dockerfile as authoritative only after Railway confirms it. |
| Health and readiness | `/api/health` always returns `{"status":"healthy"}`. No database query, migration-state check, storage check, or dependency check is performed. `railway.json` has no healthcheck path or timeout. | **Blocker:** Railway can mark a container healthy while the database is unavailable or the schema is incomplete. | Add separate liveness and readiness endpoints; readiness must fail closed on DB/schema incompatibility. Configure Railway to use readiness. |
| Migration execution | `app.main` calls `Base.metadata.create_all()` and `run_startup_migrations(engine)` during module import, before FastAPI is created. | **Blocker:** every starting replica may attempt DDL; app startup and schema change are coupled. There is no PostgreSQL advisory lock or migration-only release phase. | Move migrations into a single, explicit pre-deploy/release job with a DB lock. App processes must only verify the expected schema version. |
| Migration inventory | The tracked startup registry contains only `2026_07_29_settlement_cash_adjustments` and `2026_07_30_trailer_resale_plan`; dozens of legacy migration scripts remain outside it. `create_all()` cannot upgrade existing tables. | **Blocker:** a fresh DB and an old production DB can reach materially different schemas. | Establish one authoritative ordered migration chain from an agreed baseline; test both empty-bootstrap and production-snapshot upgrade. |
| Migration ledger | `schema_migrations` records only ID and timestamp. Migration completion is inserted after DDL in a separate transaction. | **At risk:** no checksum, release SHA, start/failure state, duration, actor, or failure detail. A crash can apply DDL without recording completion. | Extend the ledger and make each migration transactional where PostgreSQL permits. Record failures and release identity. |
| Legacy migration safety | `run_all_production_migrations.py` prompts whether to continue after failure. Some scripts rebuild/drop tables, delete duplicate journal entries, or recalculate financial balances. | **Blocker:** partial success and silent data correction are possible; the master runner is unsuitable for an unattended production release. | Never execute the legacy master runner in production. Port only reviewed migrations into the authoritative chain, with before/after assertions and an approved data-change manifest. |
| Backups and restore | Repository docs mention Railway automatic backups and exports, but contain no verified retention, restore rehearsal, RPO/RTO, checksum, or external logical snapshot process. | **Blocker:** recoverability is asserted, not demonstrated. | Verify Railway backup/PITR settings live; create a pre-release manual snapshot and encrypted logical dump; perform a timed staging restore rehearsal. |
| Rollback | Railway can roll back an application image, but the repository has no schema compatibility matrix or database rollback procedure. | **Blocker:** application rollback does not undo schema/data migrations. | Require expand/contract compatibility. Prefer app rollback plus forward DB repair. Database restore/PITR is an emergency, separately approved cutover. |
| Audit logging | Financial records have creation timestamps in places, but no actor, request/correlation ID, old/new values, release ID, immutable audit event, or durable export. Several routes hard-delete settlements, repairs, tenants, trucks, accounts, and journal data. | **Blocker:** material financial changes cannot be reconstructed reliably. | Implement append-only audit events and retention/export before rebuild release. Destructive actions need explicit authorization and audit records. |
| Period lock | No accounting-period/close model or write guard was found. | **Blocker:** historical periods can be changed after reports are relied on. | Add tenant-scoped period states and enforce the lock server-side on every direct and side-effecting financial write. |
| Report versions | Reports are calculated from current mutable rows; no immutable report snapshot/version, inputs hash, generation release, supersession link, or approval state was found. | **Blocker:** previously issued reports are not reproducible. | Add immutable report versions and a documented correction/supersession workflow. |
| Journal correctness | A legacy migration adds `journal_entries.deleted_at`, but the ORM model does not declare it. Service behavior checks for the ORM attribute and therefore does not use soft delete. | **Blocker:** intended soft-delete semantics are not active in current code. | Align model and migration, then prove query-wide exclusion and audit behavior. |
| Observability | Railway captures stdout/stderr, but application logging is mostly unstructured `print`/default logging. No error tracker, request latency/error telemetry, business invariant metrics, deploy annotations, or alert policy is configured in the repo. | **At risk:** infrastructure signals alone cannot detect a financially wrong report. | Add structured logs and application-level telemetry; alert on readiness, 5xx, migration failure, report-generation failure, and invariant violations. |
| Persistent files | Uploads fall back to the deployment filesystem when Cloudinary is absent; Railway service storage is ephemeral. | **Blocker if fallback is possible in production:** source documents can disappear across deploys. | Fail production startup if durable object storage is not configured, or mount and back up a verified persistent volume. Include object inventory in reconciliation. |
| Automated evidence | No migration-runner tests, PostgreSQL migration rehearsal, backup/restore test, period-lock test, report-version test, or release canary suite was found. | **Blocker:** the highest-risk path has no automated proof. | Add these tests and retain results with the release record. |

## 2. Release invariants

The release is acceptable only if all of these remain true:

1. Production data is never used as the write target during rehearsal.
2. A database identity query is recorded immediately before every database command.
3. Every tenant remains isolated; cross-tenant foreign-key or journal-line ownership mismatches are zero.
4. Every journal entry balances exactly: total debits equal total credits.
5. Every issued report can be reproduced from an immutable version, with the code release and input boundary recorded.
6. Locked periods reject creates, updates, deletes, imports, recalculations, and indirect side effects unless an authorized reopen event exists.
7. Application rollback remains compatible with the post-migration schema.
8. Pre-release recovery artifacts are verified before production DDL begins.
9. Reconciliation compares the same tenant set and period boundary before and after deploy.
10. Secrets, full connection strings, source PDFs, and bank data never appear in logs or release artifacts.

## 3. Required release record

Create one restricted release record per candidate. Do not store secrets in it.

```text
release_id:
candidate_git_sha:
previous_git_sha:
railway_project_id:
production_environment_id:
staging_environment_id:
application_service_id:
production_database_service_id:
staging_database_service_id:
production_region:
replica_count:
builder_and_root_directory:
deployment_trigger_and_branch:
app_domain:
readiness_path_and_timeout:
expected_schema_head:
migration_ids_and_checksums:
backup_policy_and_retention:
manual_backup_id_and_timestamp:
logical_dump_filename_sha256_and_size:
staging_restore_started_finished:
rehearsal_result:
baseline_artifact_sha256:
canary_tenants_and_periods:
change_window:
release_operator:
database_operator:
product_delivery_approver:
approval_gate_results:
production_deployment_id:
postdeploy_artifact_sha256:
final_decision:
incident_or_rollback_reference:
```

## 4. Approval gates

| Gate | Decision owner | Required evidence | Approval authorizes |
|---|---|---|---|
| A — Audit acceptance | Product & Delivery Lead | Section 1 reviewed; blockers assigned; live topology inventory attached | Read-only preflight and staging plan only |
| B — Snapshot and staging rehearsal | Product & Delivery Lead + database operator | Exact production/staging identities; recovery policy; data-handling plan; candidate SHA | Manual backup/logical dump and mutations confined to staging |
| C — Rehearsal acceptance | Product & Delivery Lead | Successful restore, migration, canary, rollback rehearsal, timings, reconciliations, no unresolved severity-1/2 issue | Scheduling a production change window |
| D — Production migration authorization | Product & Delivery Lead + database operator | Fresh backup verified; baseline captured; compatibility matrix; rollback target visible; communication ready | The listed production migration IDs only |
| E — Application rollout authorization | Product & Delivery Lead | Migration success and schema verification; readiness configured; old application remains compatible | Deploying the exact approved candidate SHA |
| F — Emergency restore/cutover | Product & Delivery Lead + database operator | Declared incident, expected data-loss window, last good time, failed forward-repair rationale, stakeholder acknowledgement | PITR/restore and connection cutover only |

Silence, a green build, `200 OK`, or Railway showing `Active` is not approval.

## 5. Phase 0 — make the release mechanism safe

These are production-release prerequisites, not steps to improvise during the change window.

### 5.1 Establish one migration authority

- Replace import-time migration execution with a dedicated migration command/job.
- Acquire a PostgreSQL session-level advisory lock before reading or changing the migration ledger. Exit if the lock cannot be obtained within the approved timeout.
- Add a schema compatibility identifier to the application and a migration ledger with: migration ID, checksum, started/finished timestamps, status, release SHA, operator/job identity, and error summary.
- Fail on a checksum change to an already-applied migration.
- Run migrations non-interactively with `ON_ERROR_STOP`; never continue after failure.
- Use expand/contract changes:
  1. Add nullable/new structures and dual-compatible reads/writes.
  2. Backfill in bounded, observable batches.
  3. Switch reads only after reconciliation.
  4. Remove old structures in a later release after the rollback window.
- For each migration, document lock level, expected duration, table size, transaction behavior, retry behavior, and forward-repair path.
- Prohibit unreviewed data deletion, deduplication, balance replay, constraint replacement, table rebuild, or `DROP` statements.

### 5.2 Add release-grade probes

- `/api/live`: process event loop responds; no dependency calls.
- `/api/ready`: database `SELECT 1`, expected schema head, required durable-storage configuration, and critical dependency configuration all pass within a bounded timeout.
- Readiness returns non-200 while a blocking migration is in progress or schema compatibility fails.
- Configure Railway healthcheck to `/api/ready`; set a timeout longer than normal startup but shorter than the rollback decision threshold.
- Include release SHA and schema head in a protected diagnostic response or structured startup log, not in a public secret-bearing payload.

### 5.3 Implement audit, period locks, and report versions

Minimum period-lock contract:

- Tenant-scoped period with `start_date`, `end_date`, `status` (`open`, `closing`, `locked`, `reopened`), version, actor, reason, and timestamps.
- The API, import paths, repair/settlement side effects, journal generation, resets, backfills, and maintenance scripts all call the same server-side guard.
- Lock transitions use optimistic concurrency and append an audit event.
- Reopening requires elevated authorization, reason, and a new report version; it never edits the already-issued report artifact.

Minimum report-version contract:

- Immutable tenant, report type, period boundary/as-of date, version number, status, generated timestamp, release SHA, schema head, normalized input hash, output hash, and supersedes/superseded-by link.
- Issued versions cannot be overwritten or deleted through normal application paths.
- Corrections create a new version and preserve the old artifact and audit trail.

Minimum audit event:

- Tenant, actor identity, action, entity type/ID, occurred-at, request/correlation ID, release SHA, before/after or field-level delta, reason, period-lock context, and source IP/session metadata where appropriate.
- Append-only storage with access control, retention, and export outside ordinary application deletion paths.
- Never log passwords, session cookies, `DATABASE_URL`, Cloudinary secrets, bank account numbers, source document contents, or raw sensitive payloads.

## 6. Phase 1 — read-only live preflight

Do not link this worktree or run Railway commands against a project until Gate A identifies the exact project and environment. Once authorized, capture—not change—the following:

1. Railway project, environment, service, and database IDs; project name is insufficient.
2. GitHub repository, branch, commit SHA, auto-deploy trigger, root directory, builder/Dockerfile selection, region, replica count, restart policy, domains, and current/previous rollback-capable deployments.
3. Variable **names and references only**. Confirm required secrets exist without printing values. Verify sealed variables required by a duplicated environment will be re-supplied.
4. PostgreSQL major version, database size, volume size/free space, connection limits, HA/PITR state, manual/scheduled backup policy, retention, latest successful backup time, and restoration limitations.
5. Railway log retention, active monitors, notification recipients, and external telemetry destination.
6. Object storage provider/bucket/cloud name and object count. Production must not use local upload fallback.
7. Current schema migration ledger and actual catalog shape.

Before any SQL, prove the target without displaying credentials:

```sql
SELECT
  current_database() AS database_name,
  current_user AS database_user,
  inet_server_addr() AS server_address,
  inet_server_port() AS server_port,
  version() AS postgres_version,
  pg_is_in_recovery() AS is_replica,
  now() AS observed_at;
```

Abort if any identifier differs from the approved release record.

### Schema preflight

```sql
SELECT migration_id, applied_at
FROM schema_migrations
ORDER BY applied_at, migration_id;

SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

SELECT conrelid::regclass AS table_name, conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY 1, 2;
```

Compare this output with the candidate's explicit schema manifest. `Base.metadata.create_all()` success is not proof of parity.

## 7. Phase 2 — immutable baseline and recovery artifacts

Run only after Gate B.

### 7.1 Capture the reconciliation baseline

Run the queries in Section 11 with the approved tenant and period parameters. Export machine-readable results, hash them, and store the files in restricted release storage. Record query version, database identity, snapshot time, and transaction boundary.

For a stable multi-query baseline, use a read-only repeatable-read transaction:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
-- Run the approved baseline queries.
COMMIT;
```

### 7.2 Create two independent recovery artifacts

1. **Railway recovery point:** create a manual volume/database backup or verify the approved PITR point. Record the ID/time and confirm it is restorable under the current plan and retention policy.
2. **Portable logical snapshot:** create a PostgreSQL custom-format dump with no owner/ACL metadata. Store it encrypted outside the application service filesystem, record byte size and SHA-256, and test-list its catalog.

Illustrative operator commands (placeholders must be resolved from the approved record; do not paste URLs into tickets or logs):

```bash
umask 077
pg_dump --format=custom --no-owner --no-acl --verbose \
  --file="$RELEASE_SNAPSHOT_PATH" "$SOURCE_DATABASE_URL"
sha256sum "$RELEASE_SNAPSHOT_PATH"
pg_restore --list "$RELEASE_SNAPSHOT_PATH" > "$RELEASE_SNAPSHOT_CATALOG_PATH"
```

On macOS, use `shasum -a 256` if `sha256sum` is unavailable.

Backup acceptance requires:

- command exit status zero;
- non-zero dump size and readable catalog;
- checksum copied into the release record;
- snapshot timestamp inside the approved change window;
- Railway backup/PITR status verified independently;
- enough time and capacity to restore within the stated RTO.

## 8. Phase 3 — staging-clone rehearsal

Railway environment duplication copies service configuration, not a verified copy of production data. Sealed variables are not copied. Treat the staging database as empty until proven otherwise.

1. Duplicate the production environment into a persistent, isolated staging environment.
2. Do **not** approve the staged deployment yet.
3. Attach a new staging PostgreSQL service/volume. Never point staging at the production database.
4. Replace outbound integrations with sandbox/disabled endpoints; disable email, webhooks, scheduled jobs, imports, and external side effects.
5. Supply staging-only sealed variables. Confirm every database/object-store hostname differs from production.
6. Restore the logical snapshot into the empty staging database. Use `--exit-on-error --single-transaction --no-owner --no-acl` where the dump contents support one transaction. Do not use `--clean` unless the database operator has re-proven that the target is disposable staging.
7. Record restore duration, warnings, row counts, and checksum of the source dump.
8. Deploy the **previous** application SHA first and prove the clone matches the production baseline.
9. Run the candidate migration job exactly once. Capture lock acquisition, migration IDs/checksums, durations, row counts, and ledger results.
10. Deploy the candidate application SHA and execute Section 10 canaries and Section 11 reconciliation.
11. Exercise period behavior: open write succeeds; locked-period direct and indirect writes fail; authorized reopen creates an audit event and a new report version; old report hash remains unchanged.
12. Exercise report behavior for at least one tenant with historical data, one current period, one closed period, one empty period, and one as-of balance-sheet date.
13. Rehearse application rollback to the previous SHA without reverting the database. Re-run readiness and read-only financial canaries.
14. Rehearse the documented forward repair on a disposable clone. A destructive restore rehearsal must use a separate disposable environment, never the accepted staging evidence environment.
15. Record total RTO and the latest recoverable point/RPO.

Rehearsal passes only when results are deterministic on a fresh clone and no step depends on an interactive prompt or an undocumented manual SQL edit.

## 9. Phase 4 — production orchestration

Run only after Gates C and D. One operator executes; one observes and records.

### 9.1 Freeze and baseline

1. Announce the approved change window and establish an incident channel.
2. Pause imports, backfills, schedulers, and nonessential financial writes. If the app lacks a reliable maintenance/read-only mode, stop: this is a blocker.
3. Confirm no long-running transactions or conflicting DDL.
4. Re-run database identity, schema, and recovery-point checks.
5. Capture a fresh repeatable-read baseline and both recovery artifacts from Section 7.
6. Verify the previous deployment still shows a rollback action and note its deployment ID.

### 9.2 Run migrations

1. Confirm the candidate SHA, expected current schema head, next migration IDs/checksums, and forward-repair plan.
2. Run the dedicated migration job once with advisory locking and fail-fast behavior.
3. Stream structured logs to the release record. Never expose secrets or source financial payloads.
4. Stop on the first failed assertion or migration. Do not start the application rollout.
5. Verify ledger status, catalog shape, constraints/indexes, and targeted backfill counts.
6. Run the read-only invariant subset in Section 11.

### 9.3 Deploy application canary

Run only after Gate E.

1. Deploy the exact candidate SHA. Do not rebuild from an unpinned moving branch after approval.
2. Require `/api/ready` to pass before Railway marks the deployment active.
3. Keep the previous deployment available for the verified overlap/rollback window where topology supports it.
4. Run the canaries in Section 10 against the production domain with the designated canary tenant and read-only user first.
5. Re-enable writes in a bounded canary window only after read-only checks pass.
6. Execute one pre-approved, reversible canary write in an **open** period, verify its audit event and financial effect, then reverse it through the normal audited workflow if the product supports reversal. Do not fabricate or delete a financial transaction solely for testing.
7. Re-enable schedulers/imports one at a time and observe at least one successful cycle.

## 10. Canary checks

### Infrastructure and application

- Railway deployment is the approved ID/SHA and remains `Active`.
- `/api/live` and `/api/ready` pass; readiness reports the expected schema head.
- Authenticated API access works; unauthenticated financial API access is denied.
- Database connections, CPU, memory, disk, and network remain within the rehearsal envelope.
- No migration, constraint, timeout, 5xx, restart-loop, or missing-storage errors appear in logs.
- Source document retrieval uses durable storage and a known existing non-sensitive canary object.

### Tenant and financial behavior

- A canary user cannot read or write another tenant's data by changing headers, IDs, or query parameters.
- Income statement, balance sheet, Schedule C, general ledger, journal entry list, and tax-year summary return for approved canary periods.
- Journal entries remain balanced and every line belongs to the same tenant as its entry and account.
- Settlement/repair create, update, delete, import, and recalculation paths respect period locks.
- Locked-period attempted writes return the specified conflict/locked response and append a denied-action audit event where policy requires it.
- Re-generating an unchanged report produces the same normalized input/output hashes or a documented deterministic exception.
- Issued report versions remain addressable and unchanged after a correction creates a superseding version.
- Soft-deleted journal entries are excluded consistently from every report and ledger query while retained for audit.

## 11. Post-deploy reconciliation

Parameterize every query by the approved tenant and period. Run the same query version before and after. Investigate differences; do not normalize them away.

### 11.1 Inventory counts

```sql
SELECT t.id AS tenant_id, t.name,
       COUNT(DISTINCT tr.id) AS vehicles,
       COUNT(DISTINCT s.id) AS settlements,
       COUNT(DISTINCT r.id) AS repairs,
       COUNT(DISTINCT je.id) AS journal_entries,
       COUNT(DISTINCT jel.id) AS journal_lines
FROM tenants t
LEFT JOIN trucks tr ON tr.tenant_id = t.id
LEFT JOIN settlements s ON s.truck_id = tr.id
LEFT JOIN repairs r ON r.truck_id = tr.id
LEFT JOIN journal_entries je ON je.tenant_id = t.id
LEFT JOIN journal_entry_lines jel ON jel.journal_entry_id = je.id
GROUP BY t.id, t.name
ORDER BY t.id;
```

For authoritative counts, also query each table separately; multi-join distinct counts are a summary, not the only evidence.

### 11.2 Journal balance

```sql
SELECT je.tenant_id, je.id AS journal_entry_id,
       SUM(jel.debit) AS debits, SUM(jel.credit) AS credits,
       SUM(jel.debit) - SUM(jel.credit) AS difference
FROM journal_entries je
JOIN journal_entry_lines jel ON jel.journal_entry_id = je.id
GROUP BY je.tenant_id, je.id
HAVING SUM(jel.debit) <> SUM(jel.credit)
ORDER BY ABS(SUM(jel.debit) - SUM(jel.credit)) DESC;
```

Expected result: zero rows.

### 11.3 Cross-tenant ownership

```sql
SELECT COUNT(*) AS mismatched_lines
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
JOIN chart_of_accounts coa ON coa.id = jel.account_id
WHERE jel.tenant_id <> je.tenant_id
   OR jel.tenant_id <> coa.tenant_id
   OR je.tenant_id <> coa.tenant_id;
```

Expected result: `0`.

### 11.4 Source-to-journal coverage

```sql
SELECT tr.tenant_id, je.reference_type,
       COUNT(*) AS journal_entries,
       COUNT(DISTINCT je.reference_id) AS distinct_sources
FROM journal_entries je
LEFT JOIN trucks tr ON tr.id = je.truck_id
WHERE je.reference_type IN ('settlement', 'repair')
GROUP BY tr.tenant_id, je.reference_type
ORDER BY tr.tenant_id, je.reference_type;
```

Pair this with explicit missing-source and duplicate-active-reference queries based on the final soft-delete schema. Differences from baseline require source-level review.

### 11.5 Period totals

```sql
SELECT tr.tenant_id,
       COUNT(*) AS settlement_count,
       SUM(COALESCE(s.gross_revenue, 0)) AS gross_revenue,
       SUM(COALESCE(s.expenses, 0)) AS settlement_expenses,
       SUM(COALESCE(s.net_profit, 0)) AS net_profit,
       SUM(COALESCE(s.cash_settlement_amount, 0)) AS cash_settlement_amount
FROM settlements s
JOIN trucks tr ON tr.id = s.truck_id
WHERE s.settlement_date BETWEEN :period_start AND :period_end
GROUP BY tr.tenant_id
ORDER BY tr.tenant_id;

SELECT tr.tenant_id, COUNT(*) AS repair_count,
       SUM(COALESCE(r.cost, 0)) AS repair_cost
FROM repairs r
JOIN trucks tr ON tr.id = r.truck_id
WHERE r.repair_date BETWEEN :period_start AND :period_end
GROUP BY tr.tenant_id
ORDER BY tr.tenant_id;
```

### 11.6 Trial balance

```sql
SELECT je.tenant_id,
       SUM(jel.debit) AS total_debits,
       SUM(jel.credit) AS total_credits,
       SUM(jel.debit) - SUM(jel.credit) AS difference
FROM journal_entries je
JOIN journal_entry_lines jel ON jel.journal_entry_id = je.id
WHERE je.entry_date <= :as_of_date
GROUP BY je.tenant_id
ORDER BY je.tenant_id;
```

Expected difference for each tenant: `0.00`.

### 11.7 Report reconciliation

For each canary tenant/period, compare before and after at minimum:

- report version ID, normalized input hash, output hash, generation SHA, and schema head;
- income statement revenue, each expense category, total expenses, and net income;
- balance-sheet assets, liabilities, equity, and accounting-equation difference;
- Schedule C gross receipts, each tax line, total expenses, and net profit;
- general-ledger opening balance, period debits/credits, and closing balance by account;
- tax-year summary totals;
- source settlement/repair counts and amounts feeding the report.

Any unexplained cent-level difference is a failure. Approved intended differences need a source-record drill-down and signed reconciliation note.

## 12. Rollback and recovery decision tree

### Roll back the application immediately when

- readiness fails after the approved timeout;
- sustained 5xx/error rate exceeds the rehearsed threshold;
- authentication or tenant-boundary behavior regresses;
- reports cannot be generated but data invariants still hold;
- the candidate is wrong and the previous application is proven compatible with the migrated schema.

Action: use Railway's rollback action for the recorded previous deployment, then re-run readiness and read-only reconciliations. Railway application rollback restores the prior image/configuration; it does **not** reverse database changes.

### Stop writes and forward-repair the database when

- migration is partially applied but recovery artifacts are intact;
- a constraint/index/backfill is wrong but source data remains complete;
- the old and new applications are unsafe against the current schema;
- reconciliation differs in a bounded, understood set.

Action: enter maintenance/read-only mode, preserve logs and a new incident snapshot, run only the rehearsed forward repair after approval, and reconcile again.

### Invoke Gate F and restore/PITR only when

- destructive corruption or unbounded financial divergence is confirmed;
- source rows or audit history cannot be reconstructed safely by forward repair;
- the expected data-loss interval is understood and accepted;
- the restore target/time was tested and stakeholders accept the RPO.

Prefer PITR to a new sibling PostgreSQL service when available, validate it in isolation, reconcile to the last good point, and only then perform a controlled connection cutover. Do not restore over the only production database as the first response. Keep the original service read-only until the incident is closed.

### Mandatory abort/rollback criteria

- wrong project/environment/database identity;
- no fresh verified recovery point or failed dump checksum/catalog check;
- backup age, RPO, or restore time outside the approved bound;
- migration lock cannot be acquired;
- unexpected migration ID/checksum or dirty migration state;
- DDL exceeds the rehearsed lock/duration threshold;
- any cross-tenant mismatch or unbalanced journal entry;
- missing/different source counts not explicitly explained;
- locked-period mutation succeeds;
- issued report artifact/hash changes in place;
- production uses ephemeral upload storage;
- previous deployment is not rollback-capable and no alternate recovery plan is approved;
- observability is unavailable during the change window.

## 13. Post-deploy observation and closeout

1. Observe continuously for the first 30 minutes, then at 1 hour, 4 hours, 24 hours, and after the first scheduled import/report cycle.
2. Track readiness, restarts, 5xx, request latency, DB connections/locks, migration/report errors, audit-event failures, invariant metrics, resource usage, and object-storage errors.
3. Re-run the targeted reconciliation after the first real write/import and at 24 hours.
4. Keep the recovery artifacts and previous compatible deployment through the approved rollback window.
5. Do not remove old columns or compatibility code in this release.
6. Close the release only after the Product & Delivery Lead signs the reconciliation and no unresolved financial discrepancy remains.
7. Record lessons, actual RTO/RPO, and any runbook correction before the next release.

## 14. Handoff to Product & Delivery Lead

### Decision requested

Accept the **NO-GO** audit baseline and assign the following work before a production financial-reporting release:

1. release job with serialized, checksummed migrations and schema compatibility checks;
2. database-aware readiness plus Railway healthcheck configuration;
3. verified Railway backup/PITR policy and timed restore rehearsal;
4. immutable audit event system;
5. tenant-scoped period locks enforced on every write path;
6. immutable, supersedable report versions;
7. current ORM/migration alignment for journal-entry soft delete;
8. durable production document storage enforcement;
9. structured logs, application telemetry, and alert ownership;
10. automated PostgreSQL migration, reconciliation, period-lock, report-version, and canary tests.

### Live evidence still required

- Railway project/environment/service IDs and topology;
- active production SHA and last rollback-capable deployment;
- actual database version/size/HA/PITR/backup status and retention;
- live schema catalog and migration ledger;
- current object-storage configuration;
- monitor/alert configuration and recipients;
- acceptable RPO, RTO, maintenance window, and canary tenants/periods.

Until those items and the blocking controls are resolved, do not deploy or mutate production for the financial-reporting rebuild.

## 15. Platform references

- Railway environments and duplication: <https://docs.railway.com/environments>
- Railway variables and sealed-variable caveats: <https://docs.railway.com/variables>
- Railway deployment actions and rollback: <https://docs.railway.com/deployments/deployment-actions>
- Railway deployment healthcheck behavior: <https://docs.railway.com/deployments/reference>
- Railway backups: <https://docs.railway.com/volumes/backups>
- Railway point-in-time recovery: <https://docs.railway.com/volumes/point-in-time-recovery>
- Railway observability: <https://docs.railway.com/observability>
- Railway logs and retention: <https://docs.railway.com/observability/logs>
