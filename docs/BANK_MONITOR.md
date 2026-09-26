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
- Password login reads `BANK_MONITOR_USERNAME_<tenant ID>` and
  `BANK_MONITOR_PASSWORD_<tenant ID>` from the worker environment only. Add these
  through the hosting provider secret settings, never chat or shell command text.
  A secure server MFA interface is still unimplemented; keep the worker disabled
  until operator recovery and a real server connection have been verified.

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
or `VITE_*` variables. The reader now consumes tenant-specific username/password runtime secrets only
when the saved session cannot show accounts. The login URL and field selectors
were inspected on the actual Truliant login page. No bank credentials were added
and no real credential submission was performed during implementation.

The reader expects a dedicated, pre-provisioned private browser profile on the
worker host. It can submit credentials once if its session has expired. It does not extract cookies from Codex or personal
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

## Login recovery guard

Before filling credentials, the reader verifies the exact HTTPS login origin and
path. It creates an empty private `.login-needs-review` file inside the profile
before submitting. Only a successfully loaded account view clears that file.
MFA, rejected credentials, timeouts and interrupted attempts leave it in place,
preventing automatic password retries across restarts and subsequent daily runs.
The marker contains no credentials or bank response text.

`credentials_required` means worker secrets are missing; `mfa_required` means the
observed MFA URL was reached; `login_review_required` means operator review is
required before another attempt. These states do not complete MFA. No code-entry
endpoint, remote browser access, CAPTCHA solver, or security-question automation
is implemented. Do not clear the marker automatically. An operator must first
resolve the sign-in on the dedicated server profile with the worker stopped, then
remove the empty guard file if another credential attempt is appropriate.

Validation: 21 synthetic tests pass across `tests/test_bank_monitor.py` and
`tests/test_bank_login.py`. These verify durable retry blocking, origin checks,
missing credentials, and simulated MFA/success, not real server authentication.

## Friday income repayment proposals

The user selected no extra checking reserve beyond pending debits. The Friday
17:30 Eastern daily run can now include a separate repayment proposal, with an
explicit repayment order independent of the borrowing order: Preferred/business
credit line first, then HELOC. Select the actual sources in the app; nicknames
never establish account identity. Existing saved configurations default to
repayment disabled. The local synthetic preview demonstrates the settings only.

The calculation requires fresh verified evidence for every monitored checking
account: current balance, pending debit total, cash withdrawable without credit
coverage after holds, and eligible cleared business/salary income for that Friday.
Transfers, credit draws, pending/unavailable deposits and older income must not be
classified as eligible income. The reader does not yet supply these fields, so a
live Friday run returns `repayment_data_required` rather than guessing.

For each checking account, the repayment cap is the lesser of eligible income and
(minimum of current balance minus pending debits and verified withdrawable cash)
minus the reserve. Using the minimum avoids subtracting holds twice. Any checking
account below its reserve blocks all repayments. A nonzero shortfall target set
through the API is also preserved. Each credit source requires its full verified
payoff amount; minimum payment/amount due and available credit cannot substitute.
The remaining debt is shared across checking accounts, preventing overpayment.

Proposals are saved within the existing unique tenant/date daily run and never
move money. There is no executed-payment ledger or automatic retry. Deposits
arriving after the Friday check are not automatically swept. Server connection,
income identification, pending-debit extraction, payoff verification and any
financial execution workflow remain unfinished. These proposals do not guarantee
fee avoidance or reserve for bills the bank has not yet shown as pending.

Validation after this addition: 31 focused synthetic tests pass, frontend
TypeScript/Vite build passes, and the local browser accepted and saved business
credit first / HELOC second with repayment proposals enabled for the synthetic
tenant. No production settings, bank credentials or banking balances changed.

### Manual repayment check and preparation

An enabled repayment policy can also be evaluated on demand without waiting for
Friday at 5:30 p.m. `Check bank now` first discovers the current account list and
persists newly detected checking and credit accounts without removing previously
configured accounts. The repayment drawer prefills each checking account's
posted balance, pending debits, and cash remaining after those debits from the
latest read. The user confirms how much cleared incoming cash in each checking
account is reimbursement income, its date, and the full payoff for every credit
source. The server applies the same reserve, income, freshness, and priority
rules as the scheduled calculation; only the Friday calendar gate is skipped.

Each manual evaluation has its own tenant-scoped `bank_repayment_runs` record and
appears in run history. A reviewed proposal can be added to the transfer queue
once. A second repayment proposal cannot be queued while an earlier repayment
draft remains unresolved. Repayment drafts use a unique `Rpy` memo, checking as
the source, and the configured credit account as the destination.

Extension 0.1.22 prepares the exact checking-to-credit form after the existing
extension-owned approval. It never submits the form. After the user submits in
Truliant, verification requires one exact posted debit in the checking history
and one exact posted credit in the destination history with the same amount,
date, and unique memo; ambiguous or missing matches stay unconfirmed.


## Observed history adapter update

The read-only adapter now follows configured checking cards into account history
and collects pending debit amounts only between explicit Pending and Posted
section boundaries. Pending credits never offset pending debits. Missing sections,
truncated pending lists, duplicate transaction IDs and malformed amounts stop
pending coverage; absence of a Pending section is not yet proof of zero. The app
now exposes posted-plus-pending coverage as an explicit setting. The existing
posted-only setting is preserved until changed.

When repayment proposals are requested, the reader also opens each credit source's
Account Details and collects separately labeled Balance and Accrued Interest.
Neither Amount Due nor Balance plus Accrued Interest is assumed to be a payoff.
The result and UI keep these observations separate from a verified payoff quote.
No full account numbers or transaction descriptions are persisted by this adapter.
Snapshot time starts before collection so slow navigation cannot make old balances
appear fresh at the end of a run.

The live bank UI and DOM structure were inspected. The underlying worker browser
has not been authenticated or exercised on the server. Income classification,
cash availability excluding overdraft credit, payoff verification and server MFA
remain incomplete. Earlier descriptions saying pending extraction is entirely
unimplemented are superseded by this section; production acceptance is still open.

Validation: 42 focused tests pass. The new tests cover pending debit direction,
explicit empty versus missing sections, malformed/duplicate/truncated rows, and
keeping credit balance/interest separate from payoff. No banking mutations occurred.

### Bank-reported transfer review

When Plaid is linked, **Review transfers** refreshes balances server-side and
opens a prefilled drawer. It does not require the user to copy balances, pending
amounts, or exact payoff figures. The old manual-evidence flow remains available
only when Plaid is not connected.

The review uses the lowest of current balance, available balance, and current
balance minus reported pending debits. It then protects the configured reserve
and all unfinished outgoing drafts. Incoming drafts are never treated as cash.
Checking shortfalls take precedence: credit repayments wait for checking
coverage to post. Credit allocations follow configured priority, reduce reported
outstanding debt by unfinished incoming drafts, and stop at missing debt data.
These are bank-reported estimates, not a complete pending-debit certification or
an exact payoff quote. Upcoming obligations absent from the bank data still need
to be retained by reducing/skipping suggested amounts or increasing the reserve.

Users may reduce or skip routes, then create all selected drafts in one action.
The server binds drafts to its stored five-minute snapshot, account settings,
provider connection and current queue. It rejects increased/forged routes,
expired reviews, changed settings and repeated creation. Preparation refreshes
bank balances again. Unprepared drafts from this flow can be removed; requested
or potentially submitted transfers cannot be cancelled through this action.
No extension update is needed: checking coverage uses the existing Cvr form
contract, and credit repayment uses Rpy. The user submits in Truliant.

While Bank Monitor is visible, prepared transfers are checked through Plaid at
most once per minute per transfer, including after returning to the page. Only a
unique posted debit and credit matching amount and the complete generated draft
reference can be marked automatically. Amount/date candidates without that
reference require confirmation; absent, ambiguous or delayed entries remain
unconfirmed. No additional bank login is needed for these provider reads unless
Plaid requires renewed consent. This is page-driven reconciliation, not a claim
that the unattended Friday repayment worker now has complete pending evidence.

Validation: `backend/tests/test_bank_transfer_review.py` covers reserve/pending
math, shared cash/debt, missing evidence, snapshot expiry, tampering, tenant and
action checks, duplicate creation, cancellation boundaries, checking preparation,
balance changes and automatic-reference matching. Browser QA uses isolated local
test data; production transfer submission is not a QA step.
