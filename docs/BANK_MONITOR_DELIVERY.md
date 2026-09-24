# Bank monitor delivery checklist

Updated 2026-09-14. This is the authoritative completion checklist; historical
implementation notes in BANK_MONITOR.md are not deployment evidence.

## Current production evidence

Railway project: Elis Pro Tech App (2ca38ba9-ce81-424b-b7dd-ece2dd01aac2).
Production environment: fd4c6a83-6e5f-4048-addb-bf14993957b1.
Live inspection confirms only web and Postgres services. Web runs repository
mecaniser/elis-logistics-manager at e0f9993e5b290ae55769d2f00613ba3e92aaa7f2.
No bank-monitor worker service exists. No bank-monitor changes are deployed.

## Delivery order and acceptance evidence

1. [ ] Deploy the web bank-monitor routes and additive tables with existing auth.
       Verify the production tenant ID and its server-managed allowlist.
2. [ ] Deploy a separate private worker with one replica and a persistent profile
       volume. Confirm image starts successfully with scheduled checks disabled.
       Reconcile the web service's active database before assigning DATABASE_URL.
3. [ ] User enters username/password into worker-only hosting secrets:
       BANK_MONITOR_USERNAME_<verified tenant ID> and
       BANK_MONITOR_PASSWORD_<verified tenant ID>.
       Provision BANK_MONITOR_PROFILE_<verified tenant ID> with private ownership.
       Never request secret values in chat or log them.
4. [ ] Implement and verify server-side MFA recovery and a one-shot read-only
       check. Success means both real checking accounts and both credit sources
       match the bank's displayed values; synthetic tests do not satisfy this.
5. [ ] Verify income classification, usable cash excluding borrowing, pending
       debits and full payoff amounts. Keep repayments blocked until proven.
6. [ ] Add failure notifications and worker health reporting, then enable daily
       17:30 America/New_York scheduling. Verify an actual scheduled run and an
       authentication-failure alert.
7. [ ] Resolve financial execution separately. No transfer executor exists.
       Assistant tools cannot submit consequential bank transfers. Any live
       transfer test must be submitted by the user through the bank. Deployment
       alone does not fulfill the requested unattended money movement.

Next engineering milestone: production worker deployment and authenticated,
read-only one-shot collection. Credentials and MFA require user participation;
no production transfer is part of this milestone.


## Assisted Chrome milestone — current local candidate

Implemented: tenant-scoped reviewed whole-charge draft queue; Cvr memo validation;
one-time atomic preparation claim; Chrome extension handoff; current-date,
whole-charge credit-capacity and occupied-form checks; separate preparation status;
posted source/destination matching with hashed evidence and reuse rejection.
The extension never clicks transfer submission or scheduling controls.

Verified: 42 existing backend tests passed before the new draft endpoints; all 9
new endpoint tests now pass, as do 10 simulated extension tests. TypeScript/Vite
build passes. The local synthetic browser saved a draft and displayed an actionable
missing-extension error without claiming it. No real transfer was executed.

Pending: user approval/installation in Google Chrome; production account
configuration; installed-extension form-fill acceptance; user-submitted transfer
and matching acceptance; safe reset/recovery UI; automatic bank-charge ingestion;
server deployment and notification delivery. Current Chrome pilot uses a manually
reviewed draft, not an automatically populated charge queue. A Chrome restart or
lost tab requires operator review; do not bypass unresolved draft locks.

Installation and precise permission scope are documented in
browser-extension/elis-bank-assistant/README.md. Installation approval is pending
in this conversation. No deployment or bank credential changes were made.

### Approval expiry recovery — 2026-09-14

- Live pilot: correct Chrome profile connected; actual account suffixes configured locally. Union County draft reached extension approval, but the user confirmed the approval tab disappeared before they clicked. No successful form preparation or transfer is established.
- Local fix: extension 0.1.2 returns PREPARATION_NOT_STARTED only for explicit approval timeout/cancel before bank-tab creation. ELIS returns that requested draft to reviewed; unknown failures remain locked. Ping now reports manifest version. The UI explains the two-minute deadline.
- One-time local recovery: restored only charge reference `3304-20260914-UNION-COUNTY-11820` from preparation_failed to reviewed after user confirmation, unchanged bank balances, and no prepared bank tab. No production data or banking action performed.
- Validation: 13 extension tests, 10 draft API tests, TypeScript/Vite build passed. Local preview restarted and the real draft visibly shows Ready to prepare.
- Outstanding: user must reload installed extension to 0.1.2, then live form-preparation acceptance and user-submitted transfer/history verification. Server deployment and scheduled worker remain incomplete.
- Trust limit: not-started outcome remains authenticated client-reported, not cryptographically attested. Extension active-draft locking still rejects another preparation if a bank operation was already started.

### Live history verification finding — 2026-09-14

- The user submitted the prepared $118.20 Union County transfer and supplied visible posted entries in checking 3304 and Preferred Line of Credit 2829 with the expected amount and memo.
- Extension 0.1.2 stopped during checking-history verification because Truliant rendered two identical responsive `h2` account headings. The verifier incorrectly treated duplicate renderings of one identity as conflicting accounts.
- Extension 0.1.3 accepts repeated identical heading text while still rejecting missing or conflicting identities. Known verification errors are now returned to ELIS without exposing page data.
- Validation: 15 extension tests pass, including identical-heading acceptance and conflicting-heading rejection. Live extension reload and final two-history match remain outstanding.

### Extension reload verification recovery — 2026-09-14

- Live pilot exposed that reloading the unpacked extension clears its session-only active-draft binding. ELIS retained the submitted draft as `prepared_awaiting_submission`, so verification correctly refused with `No active preparation for this draft.`
- Extension 0.1.4 adds an extension-owned approval step that can rebind only read-only history verification. It opens the bank home page and never opens the transfer form or runs form preparation.
- ELIS supplies the Eastern creation date for the same-day pilot draft and automatically resumes `ELIS_VERIFY` after the user approves reauthorization.
- Validation: 16 extension tests, 10 draft API tests, and the TypeScript/Vite build pass. Live reauthorization and final history match remain outstanding.

### Credit-source navigation timing — 2026-09-14

- Live 0.1.4 reauthorization reached checking 3304 and visibly loaded its matching posted deposit, then stopped before opening credit line 2829 with `Sign in or open the bank account to verify.`
- Extension 0.1.5 waits for the bank home navigation to complete before polling account cards and extends the iframe/card readiness window to 30 seconds. It remains read-only during verification.
- Validation: all 16 extension tests pass. Live two-account verification remains outstanding.

### Pilot operator cleanup — 2026-09-14

- Chrome inspection confirmed the installed extension was still 0.1.5 when the user retried; the 0.1.6 isolated-tab fix had not loaded.
- ELIS now refuses preparation and verification when the connected extension version differs from 0.1.6, with an explicit reload message. The submitted draft label now says `Transfer submitted; history verification pending`.
- Removed the unrelated reviewed synthetic draft from the disposable local preview database so it cannot be mistaken for the real pilot transfer. No real draft or bank data was deleted.
- Validation: frontend build and all 16 extension tests pass; browser-visible queue contains only the real Union County draft. Live 0.1.6 reload and two-account verification remain outstanding.

### Embedded bank-frame messaging — 2026-09-14

- Live 0.1.6 confirmed the Chrome session was authenticated and a separately opened fresh bank-home tab rendered all configured account cards, while one-off `chrome.scripting.executeScript(... allFrames)` still failed to reach the embedded account frame.
- Extension 0.1.7 replaces one-off history-frame injection with a manifest-declared content script restricted to `https://www.truliantfcuonline.org/*`, running only in child frames. Background verification exchanges only account suffixes and exact-match inputs/results with that script.
- Form preparation remains unchanged in the top-level bank transfer page. Verification still opens isolated read-only tabs and never clicks a transfer control.
- Validation: manifest parses, frontend build passes, and all 16 extension tests pass. Live 0.1.7 reload and two-account verification remain outstanding.

### Multiple child-frame response race — 2026-09-14

- Live 0.1.7 still failed opening checking 3304 even though a separate controlled Chrome tab confirmed the same authenticated profile and exact account-card selector matched 3304.
- Root cause: Truliant has multiple child frames. An empty frame could answer `tabs.sendMessage` before the account frame, causing a false not-found response.
- Extension 0.1.8 keeps unrelated frames silent. Only a frame containing account cards may answer account-selection messages, and only a frame containing the transaction table may answer history-match messages.
- Validation: frontend build passes and all 18 extension tests pass, including explicit empty-frame silence and exact account-frame response tests. Live 0.1.8 verification remains outstanding.

### Isolated account-history tabs — 2026-09-14

- Live 0.1.5 still stopped after checking 3304 because Truliant retained the first account route when the same tab was reused for credit line 2829.
- Extension 0.1.6 opens a fresh bank-home tab for each read-only account inspection, closes it afterward, and reports the exact account suffix if an account card cannot be opened. Reauthorization itself opens no bank tab.
- Validation: all 16 extension tests pass. Live two-account verification remains outstanding.
