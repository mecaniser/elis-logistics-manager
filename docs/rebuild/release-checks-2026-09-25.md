# Main integration and release checks — 2026-09-25

## Scope and decision

Integrated current main `6a20eb3926e829ff997956f937e370ce82faff9e` into the rebuild in isolated branch `codex/rebuild-main-integration`, merge commit `975c12d`. The original checkout and its uncommitted authentication changes remain untouched. Production and the existing local review server on port 8016 were not changed.

The migration-runner conflict was resolved by retaining both the finance additive tables/immutable-history guards and main's authentication, throttle and recovery-email migrations. Tested code tree: `b67b660a35baed40ef7cea44a09b68b2c323f673`.

Integration checks are complete. This is not a clean all-green release or a completed financial cutover. The remaining items below are explicit gates, not implied approvals to deploy.

## Verification

| Check | Result |
| --- | --- |
| Backend full suite | 235 passed, 12 failed. The same 12 failures reproduce on current main in the affected repair, settlement and truck modules (baseline run: 24 passed, 12 failed). |
| Frontend and extension Node tests | 55 passed, 0 failed. |
| Frontend production build | Passed; existing large-bundle warning remains. |
| Full frontend lint | 196 errors, 32 warnings, identical to current main; comparison found no additional findings. |
| Whitespace/conflict check | `git diff --check` passed. |
| Browser smoke | Separate synthetic fixture at port 8018: sign-in, authenticated Bank Monitor, Add account/Cancel and upstream Account security/recovery-email screen passed. No accounts, transfers or credential changes submitted. Not production browser acceptance. |
| Production status (read-only) | Web SUCCESS at main SHA above; all three authorized business scopes configured, local preview flags absent. Bank worker retained Chrome reader. |
| Fresh production-copy migration | Read-only production backup restored into isolated PostgreSQL 18.6. Startup twice, all 21 existing tables / 2,363 rows preserved by sorted-row fingerprints. |
| Authentication | Signed principal accepted for all three businesses; missing authentication, missing business, foreign business and wrong principal rejected. Preview disabled. |
| Immutable ledger | All 10 update/delete guards passed; balanced temporary posting probe rolled back without changed fingerprints. |
| Restore rehearsal | Before- and after-migration dumps restored into separate databases and matched their source fingerprints. |

Private backups, connection details and inventories remain outside Git in the ignored local release evidence directory. No production migration or production data write was performed.

## Local records that must accompany release

The local review database contains 31 owner-confirmation evidence records and one payment-account identity. Comparison of existing repairs with the production copy found one changed repair cost (repair 138). These do not travel with a code push.

Prepare a reviewed, idempotent carryover for the evidence, account identity and confirmed cost correction. Preserve dependencies, original evidence identifiers, provenance and timestamps; detect changed live records before writing. Do not replace the production database or blindly copy local postings, generated reports or opening balances. Rehearse the carryover on a fresh restored copy and report differences before applying it.

## Remaining release and plan gates

1. Resolve or explicitly disposition the reproduced baseline backend failures and lint debt; do not label the full checks green.
2. Complete the reviewed local-data carryover rehearsal above.
3. Land the reviewed candidate, deploy in the agreed sequence, verify the deployed SHA, migrations, authorized access and real-record browser workflows. No deployment has occurred in this step.
4. Keep financial results provisional wherever cash, reserves, outside costs, owner repayment, financing or accounting-policy evidence is incomplete. A code release is not finalized books.
5. Continue the original sequence: repair/outside-cost reconciliation into pair retention, then historical fuel/settlement anomalies, independent mileage, and capital/HELOC history. Missing records block dependent conclusions, not unrelated engineering.

## Local runtime follow-up

Bank monitoring now precedes payment accounts and owner reimbursements. Distinct component keys prevent stale sibling sections during reconciliation. The frontend build and browser reload passed with monitoring first and accounting sections below.

Port 8016 now serves this integration worktree, including current main, using the original local review database after a SQLite backup. The original checkout's uncommitted changes remain untouched. A local-only authenticated session replaces the previous unauthenticated preview runtime. The local database has no monitored-bank configuration; production balances and bank connections were not copied or changed. Existing local card and repair evidence remain available. This supersedes the earlier statement that port 8016 still ran the older checkout.


## Release follow-through: backend green and carryover rehearsed

The twelve backend failures were stale tests, not newly introduced application defects. Repair/settlement CRUD tests now supply the existing required business header; repair creation uses the same trailing-slash form endpoint and `repair_json`/`repair_date` fields as the frontend. Decimal assertions respect the API serialization. Explicit missing-business tests still require rejection. The legacy trailer forecast test now checks debt plus remaining replacement funding ($205 + $440 = $645), with projected reserve capped at acquisition cost ($600); it does not certify actual financing payments or funded reserves. No production financial formula or access rule was weakened.

Full backend suite: **249 passed**, 16 existing deprecation warnings. This supersedes the earlier 235 passed / 12 failed result.

### Selective carryover rehearsal

Used a separate PostgreSQL database restored from the September 25 production-copy migration dump. The source review database and production were not written. Verified original content hashes for all 300 evidence records, preserved IDs, timestamps, supersession and account references, and copied those records only. They comprise 78 settlement documents, 190 repair recovery documents, 31 payment confirmations and one payment identity. Every repair review snapshot and confirmation matched the local source; none became stale. A second import added zero records.

Repair 138 changed from $238.00 to the invoice-supported $238.86 through the existing repair update function, synchronizing its legacy journal/reserve effects. Changed tables were limited to repairs, finance evidence, journal entries, journal entry lines and repair reserve ledger. No local opening events, postings, ledger lines or generated reports were imported. Processing the carried confirmations created zero new accounting events: 28 were not applicable to personal reimbursement, and three still require the owner's unreimbursed-balance answer.

Private reproducibility script and result: `backend/settlements_extracted/release-20260925/carryover-rehearsal.py` and `carryover-rehearsal-result.json` in the original checkout (ignored, not committed). This is a rehearsal, not an approved general-purpose production importer. Before application, re-read source and live records, check for changed values, take a fresh backup and run the same conflict/dependency checks. Never overwrite a newer live record.

### Frontend lint disposition

The unchanged findings classify as 188 explicit-any errors, seven unused-binding errors, one prefer-const error, 30 effect-dependency warnings and two refresh-export warnings. Full lint remains non-green. No rule was disabled and no passing full-lint claim is made. Broad type/effect refactoring remains separate engineering work; dependency warnings in particular require behavior review rather than blindly adding dependencies. Existing build/browser results remain valid because this follow-through changed tests and documentation only.

### Immediate next action

Resolve the three real personal-payment reimbursement facts, then verify their accounting path and its relationship to pair retention. Keep production deployment pending the remaining release disposition and live-record carryover application; do not equate a passing rehearsal with a deployed release or completed financial cutover.


### Historical personal payments confirmed reimbursed

Owner explicitly confirmed existing personal payments were already reimbursed, with new invoices tracked prospectively. Applied three append-only confirmation revisions locally for $455.10, $250.00 and $238.86 ($943.96 total). Earlier evidence remains preserved. Each now shows `historical_reimbursed`, $0 remaining and owner-confirmation basis. No repayment date, bank match, cash movement or additional expense was invented. Existing posted claims still require matched repayment or review; a status edit cannot silently clear them. This resolves the previously pending question about the three personal payments.

Bank Monitor displays a historical reimbursement section with paid-personally, repaid and outstanding amounts. Browser verification confirmed all three records and $0 total owed. Full backend suite passed 251 tests before the additional new-invoice isolation test; targeted owner-posting suite also verifies new invoices still create outstanding claims. Frontend build, changed-component lint and whitespace checks passed.

Carryover rehearsal repeated with 303 evidence records (34 confirmation versions, 31 current confirmations). Three current personal confirmations are historically reimbursed, 28 other confirmations remain unchanged; zero stale snapshots, zero duplicates on repeat, no ledger events created or copied. This supersedes the earlier 300-record inventory. Private confirmation manifest and refreshed rehearsal script/result remain in the ignored release evidence directory. Production remains unchanged.

Next release work: retain these revisions in the final live carryover, finish frontend lint disposition and real-record performance acceptance, then deployment checks. The historical repayment question is closed; do not ask it again without conflicting evidence.


### Repair-to-retention verification and refreshed main integration

Fixed a real omission: historical repair-register costs without an explicit new-ledger bill were absent from the retention score. They now appear as a separate management-only deduction, with repair IDs and a source link. Explicit bill/owner-advance links exclude the legacy fallback (including reversed entries awaiting correction). Personal repayment status does not erase an incurred repair cost. No ledger posting, reserve funding or cash payment is inferred by this adjustment.

Verification covers personal payment unknown/owed/reimbursed, no duplicate on posting, weekly/monthly/yearly totals, business isolation, as-of cutoff, dated trailer assignment and unassigned trailer costs. Read-only checks against local records matched the source totals: 2026 Volvo 609 repairs $1,044.14 (12 records), Volvo 603 $4,300.01 (9 records). The score remains provisional; 67 existing settlements in that annual period remain unposted, so these are not complete annual profit figures. Browser calculation details show the deduction and references.

Integrated newer main `80bb800` (PRs 56–59) cleanly, retaining Bank Monitor hierarchy and reimbursement history. Candidate code commit `8cb4060`, tested tree `a65cd4ad145b7e967fa18acc64d1d5b8a12f80b1`: backend 262 passed, frontend/extension Node 55 passed, frontend build passed. Full lint still fails with 196 errors and 32 warnings; no blanket suppression or all-green claim. The migration/authentication/immutable-history and before/after restore rehearsal passed again against the September 25 backup (original production base 6a20eb3); it is not a fresh snapshot of later production activity. Local port 8016 runs the integrated candidate; production was not deployed or changed.

Release decision: technical checks completed with lint non-green. Before landing/deployment, resolve or formally disposition frontend lint debt and refresh production data/conflict checks for final carryover. After deployment, authenticated production browser acceptance remains mandatory. These gates remain distinct from complete historical reconstruction and finalized accounting.

### Lint gate resolved; refreshed production comparison

Full frontend lint now passes with zero errors and zero warnings, without disabling rules. Replaced untyped API/error/chart values, separated context hooks from provider components, and stabilized effect callbacks while retaining explicit filter triggers. Removed the competing vehicle-total effect that excluded additional investment expenses. TypeScript/build passed; the existing bundle-size advisory remains. Full backend: 262 passed. Frontend/extension Node tests: 57 passed, including structured API-error coverage.

Browser checks on the rebuilt local app passed: legacy weekly-to-monthly dashboard, truck editor and calculated investment total, settlement search (85 Marcus results) and clearing to the 20-row initial page, legacy income statement, and finance workspace. No console errors observed. An existing legacy income-statement display formats calendar dates through UTC and can show the prior local day; this does not change the request period and remains a follow-up item.

Fetched main remains `80bb800b97989d3e56492f047ce34c17caffaf0b`, matching the live web deployment. A fresh read-only production backup contains 2,373 legacy rows across 21 tables. Startup twice, preserved fingerprints, signed access for three businesses, unauthorized/foreign rejection, ten immutable guards and both backup restores passed again.

Fresh carryover comparison still permits only 303 evidence rows and repair 138's $238.00 to $238.86 correction. The final importer encloses route commits in savepoints under one outer transaction, checks source hashes/dependencies/unchanged repair facts, and compares all review snapshots. Rehearsal verified a rollback left every table unchanged, committed import added 303 rows, and repeat import added zero. Only repairs, evidence, legacy journals/lines and reserve ledger changed; no finance events, postings, lines or reports were copied/created. All 31 confirmations match, including three historical reimbursements with no outstanding claim.

At this checkpoint production is still unchanged. Next: apply the additive schema and the verified atomic carryover, then land/deploy the candidate and verify authenticated live behavior. Keep incomplete accounting/fuel evidence provisional.

The production carryover's source volume exposed unnecessary original-byte loading in metadata-only queries. Evidence listing and repair history now defer stored file bytes; reconstruction planning also defers them until a source hash actually needs validation. Original downloads and integrity validation remain intact. A query-level regression test verifies metadata views do not select the original-byte column. Full backend rerun: **263 passed**. Business changes now explicitly refresh active settlement searches and legacy time series; lint/build remain green.
