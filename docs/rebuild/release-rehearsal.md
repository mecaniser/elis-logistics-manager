# September 24 release rehearsal

## Scope and result

Production was read only for database inspection and a custom-format backup. The rehearsal used an isolated local PostgreSQL 18.6 instance, matching production's major and minor version. Production application/schema/data were not deployed or migrated. The only production configuration change was the owner-authorized `APP_AUTH_TENANT_IDS=1,2,3`, saved with Railway `--skip-deploys` and verified by readback.

| Check | Result |
| --- | --- |
| Actual app startup twice on restored production data | Pass |
| Legacy data preservation | All 2,352 rows across 15 tables unchanged by sorted JSON row fingerprints; migration registry excluded from this preservation comparison |
| Additive finance tables | Five created, recorded migration installed |
| Pre-migration dump restored to independent database | All table fingerprints identical |
| Post-migration dump restored to independent database | All table fingerprints identical |
| Signed principal, all three businesses | HTTP 200, preview disabled |
| Missing/wrong principal | HTTP 401 |
| Missing tenant / foreign tenant selector | HTTP 400 / 404 |
| SQL immutability | UPDATE and DELETE rejected on all five finance tables |
| Exact-decimal posting probe | Balanced; entire probe transaction rolled back |
| Focused backend regression suite | 49 passed |

Private evidence lives under ignored `backend/settlements_extracted/release-20260924/`: `production-before.dump`, `after-migration.dump`, `rehearsal-result.json`, and the local connection file. Treat this folder as confidential business data. Dumps and connection file have mode 600 inside a mode 700 folder. Do not include these in Git or an accountant package. Rehearsal databases remain isolated from production.

## Repeating the rehearsal

1. Capture a fresh custom-format `pg_dump --no-owner --no-acl` with a read-only production session. Use secret injection; never write database credentials into commands, logs or reports.
2. Restore into a new isolated PostgreSQL 18 database with `pg_restore --no-owner --no-acl --exit-on-error`. Verify the target is local before importing the application: startup performs migrations.
3. Record sorted row JSON SHA-256 fingerprints and counts for every legacy table. Import `app.main` twice with only the local database URL, isolated test credentials and the approved tenant allowlist.
4. Confirm unchanged legacy fingerprints, migration registry entry, five new tables and their guards. Exercise signed accounting context requests for all allowed tenants and rejected principals/selectors.
5. In a transaction, create balanced probe lines plus evidence/events/posting/report. Test each table's UPDATE and DELETE inside savepoints, then roll back the outer transaction. Verify no probes remain.
6. Back up the migrated local database. Restore both original and migrated dumps into separate new databases and compare their complete fingerprint maps.
7. Run the finance, finance migration, retention and settlement history pytest modules. Keep evidence dated and tied to the release revision; repeat if migration/startup behavior changes.

## Recovery and deployment boundary

Before an actual deployment, capture a fresh backup and confirm the exact release revision and configuration. The migration is additive and does not backfill historical accounting. Startup records completion only after success; the migration itself is repeatable. Do not equate schema installation with reviewed historical posting.

For an application-only regression, roll back the application revision and retain the additive finance tables and records. Do not delete immutable history. If database recovery is required, stop writes, preserve a backup of the failed state, restore the chosen backup into a new database, verify its complete fingerprints, and account for every write since that backup before switching the application connection. Restoration onto production was not performed; the offline restore mechanics were verified locally.

Live signed-login verification, actual financial reconciliation, historical differences and browser acceptance remain required. The saved allowlist is not proof that the currently running service has loaded it. No frontend build or browser claims are added by this backend-only checkpoint.
