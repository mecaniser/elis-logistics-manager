# Bank Monitor: local implementation and remaining connection work

Deployment decision: server only. The Mac/Codex browser is for development and
inspection, not the scheduled runtime. No local scheduler or recurring Codex
automation is installed.

## Server deployment package

Use a separate Railway service named `bank-monitor` in the ELIS application
project. The CLI currently lists `Elis Pro Tech App` with existing `web` and
`Postgres` services; the web service's source repository and active database must
be reconciled before adding the worker. No Railway service was created or changed.

- Service root: repository root.
- Service configuration path: `/railway.bank-monitor.json` (set explicitly in
  the new service; leave the existing web service's configuration unchanged).
- Worker image: `Dockerfile.bank-monitor`, pinned Playwright and Chromium
  installation, non-root UID 10001, one replica, no public domain or web port.
- Persistent volume: `/data`. Provision each profile directory under
  `/data/profiles/` with ownership UID 10001 and mode 0700. A deployment filesystem
  alone does not preserve sessions across replacement containers.
- Worker secrets: `DATABASE_URL` referencing the verified application database,
  `BANK_MONITOR_TENANT_IDS`, and `BANK_MONITOR_PROFILE_<tenant ID>` pointing to the
  corresponding profile path. Enable only after the connection is verified using
  `BANK_MONITOR_WORKER_ENABLED=true`; the image is disabled by default.
- The web service needs `BANK_MONITOR_TENANT_IDS` plus its existing application
  authentication. Do not share bank login secrets with the frontend or web service.
- Password-login secret names and a secure server MFA interface are not yet
  implemented. Do not add unused bank passwords to Railway at this stage.

The server entrypoint rejects an implicit/local SQLite database and stops cleanly
on SIGTERM. Synthetic tests can still exercise the worker logic with SQLite;
that does not install or enable a local scheduled process.

The container configuration has not been built or deployed against Railway.
Provisioning an authenticated session on a headless server is still a blocker:
the interactive Codex session is not a server session. A protected server-side
sign-in/MFA flow must be implemented and verified before this becomes unattended.

References: [Railway configuration](https://docs.railway.com/config-as-code/reference),
[Railway service filesystems](https://docs.railway.com/services),
[Playwright browser installation](https://playwright.dev/python/docs/browsers).

Status: proposal-only implementation. Not deployed, not connected to an unattended
bank session, and not scheduled on a production host. No transfer execution code
or endpoint exists. A completed check does not mean a shortfall has been funded.

## Implemented

- `/bank-monitor` in the application, with tenant-scoped settings and 30 recent runs.
- Dedicated worker, one daily check at 17:30 America/New_York including weekends,
  daylight saving changes and same-day catch-up after a restart.
- Current posted balance shortfall to a zero target; integer cents throughout.
- Funding order entered by the user. For this request: HELOC first, Preferred Line
  of Credit second. Multiple checking accounts share source capacity in one run.
- Insufficient credit, missing accounts, ambiguous suffixes, stale readings,
  sign-in requirements and browser failures are explicit states.
- Unique tenant/date run reservation prevents duplicate daily collection.
- Read-only Truliant adapter based on observed account-card labels and iframe.
  It opens the account home page and reads balances, never transfer controls.

The parser and scheduler are covered by synthetic tests. An actual Truliant
dashboard and account history were inspected interactively, but the separate
worker's persistent-profile access has NOT been tested against the bank.

## Access and credentials

The web API requires a valid application session even when other app routes allow
auth-disabled local development. `BANK_MONITOR_TENANT_IDS` is a server-managed
comma-separated allowlist for the existing single application principal. This
does not fix the repository's broader tenant-authority gaps in other routes.

Do not put bank passwords in application forms, source control, logs, test data,
or `VITE_*` variables. Protected runtime secrets can hold bank credentials for a
future verified password-login adapter, but the current reader does not consume
username/password variables. No bank credentials were added during implementation.

The current reader expects a dedicated browser profile authenticated by the
operator on the worker host. It does not extract cookies from Codex or personal
Chrome profiles. Profile storage contains sensitive session material; keep it
outside the repository, restrict the directory to mode 0700, and restrict host
access. MFA, CAPTCHA and expired sessions require user action, not bypasses.

## Worker setup (not performed)

1. Deploy the application with its normal database/authentication configuration.
   Existing startup `Base.metadata.create_all` creates the two additive tables.
   The worker must start after those tables exist; it performs no schema setup.
2. Install Python Playwright and its Chromium runtime on a dedicated worker host.
   Provision a separate private browser profile and verify an operator sign-in.
3. Set `BANK_MONITOR_TENANT_IDS` on both web and worker to the authorized business
   IDs. Map `BANK_MONITOR_PROFILE_<tenant ID>` to its absolute profile directory.
   All accounts in a profile must be approved for that business; the UI maps only
   unique last-four suffixes and fails if suffixes collide.
4. The worker uses the same database as the web application. Configure the account
   suffixes and source order in the app. Enable the requested daily checks there.
5. Set `BANK_MONITOR_WORKER_ENABLED=true` on the worker, then supervise
   `python -m app.bank_monitor_worker` from `backend/`. Do not enable this inside
   each web worker or rely on an open Codex task to keep it running.

A sleeping/offline host cannot perform a timely check. A worker startup after
17:30 catches up once for the current Eastern date, not past dates. Failed daily
runs are retained and not silently retried. A crashed run remains `running`;
inspect the worker before recovery. There is currently no retry UI, external
notification delivery or independent worker-heartbeat alert. These are rollout
requirements before relying on this as an unattended service.

## Pending debits and fee timing

The live account history showed a pending debit separate from current balance.
The calculation engine supports explicitly verified pending debit totals, but
the bank reader does not yet extract them; the UI therefore exposes posted-only
coverage. Pending coverage submitted through the API fails closed when its data
is unavailable. Never subtract pending debits from available balance: holds may
already be included, and available balance may also include credit coverage.

Before enabling any financial execution implementation, independently verify
bank authorization/integration terms, transfer eligibility and minimums, posting
cutoffs, overdraft fee assessment timing, and the desired pending-debit horizon.
An evening check cannot be represented as a guarantee of avoiding fees.

## Verification

Use a disposable database; importing `app.main` runs existing startup migrations:

```sh
DATABASE_URL=sqlite:////tmp/elis-bank-monitor-test.db python -m pytest tests/test_bank_monitor.py -q
```

From the repository root, run `npm run build --prefix frontend` for TypeScript
and the production bundle. No tests execute bank transfers or use bank passwords.
