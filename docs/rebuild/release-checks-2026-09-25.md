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
