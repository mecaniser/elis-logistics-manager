# ELIS Bank Form Assistant — Chrome pilot

Status: version 0.1.1 local pilot, targeted security hardening and simulated tests complete; not installed or live-accepted.
No transfer submission, recurring payment, or scheduled-payment code exists.

## Install locally

1. In Google Chrome, open `chrome://extensions`.
2. Enable Developer mode, choose **Load unpacked**, and select this folder:
   `/Users/sergio_m1_promax/GitHub/elis-bank-monitor/browser-extension/elis-bank-assistant`.
3. Copy the extension ID shown on its card.
4. Open `http://127.0.0.1:18081/bank-monitor` in the SAME Chrome profile.
   The local preview login is `preview` / `local-preview-only` (synthetic app only).
5. Paste the ID into **Chrome extension ID**. This is an extension identifier,
   not a credential. Sign into Truliant in the same Chrome profile before testing.

Permission scope: the extension can read and modify pages on
`https://www.truliantfcuonline.org/*`, open a bank tab, and retain the reviewed draft and tab binding
in Chrome session storage. It does not read password fields or cookies and has
no password storage. Only the local ELIS bank-monitor page on port 18081 can send requests. Production
origin access is disabled in this pilot build. No third-party service receives
bank data. Only hashed transaction references return to ELIS for matching.

Do not confuse the synthetic preview tenant/accounts with real account setup.
The current dashboard seed uses fictional account suffixes. Do not change those
and then claim a real business has been configured or authorized in production.
An actual pilot requires the intended business/account configuration first.

## One-transfer acceptance

- Review bank history and add a draft for an uncovered whole charge with a unique
  bank charge reference and a `Cvr` memo (34 ASCII characters maximum).
- Choose a source that covers the WHOLE charge, HELOC first when sufficient;
  otherwise select Preferred Line of Credit. No splitting or sweeping credit.
- Click **Prepare in Truliant**. Review the extension-owned screen and choose
  **Approve form preparation**. The extension then opens one dedicated bank tab,
  validates source availability and today's date, and fills accounts/amount/memo.
  It refuses to overwrite an occupied form. It never clicks Make transfer.
- The user reviews and submits in the bank, including any confirmation or MFA.
- Return to ELIS and click **I finished in Truliant — check both histories**.
  This navigates the extension's bank tab, so finish the bank flow first.
- One exact posted checking deposit AND one credit-line disbursement must match
  date, amount, and memo. Pending/ambiguous matches remain unconfirmed. The result
  is reported by the user's extension, not independently verified by a server API.
- ELIS stores hashed source/destination transaction IDs with unique constraints;
  the same evidence cannot complete another draft. The extension releases its
  preparation lock only after ELIS accepts the match.

## Current limitations and recovery

Automatic charge import/matching, funding-source selection, server notification,
production deployment and mobile support remain unfinished. This pilot uses
manually reviewed drafts. Scheduled worker balances still use the older aggregate
proposal calculator; do not interpret those as charge-level executable drafts.

If login expires before preparation, sign in and inspect the dedicated bank tab.
Do not create another draft to bypass a lock. Preparation failures and uncertain
responses remain locked for review. There is not yet a safe operator reset UI.
If a tab closes or Chrome restarts, session storage may be lost: the server draft
remains locked, and recovery needs manual bank-history review. Do not clear locks
or reset statuses without reconciling the bank. This limitation blocks unattended
or general production rollout.

Matching supports the observed English `Deposit` and `Principal Disbursement`
history formats only. New formats, delayed posting, next-day posting, or identical
memos require review. Actual submitted transfer wording is not yet live-verified.

## Checks

`npm test` in this folder runs simulated extension tests. Backend draft tests cover
auth/tenant scope, account validation, repeated clicks, and evidence reuse.
Passing them does not prove the installed Chrome-to-bank flow works.


## Security review 0.1.1

Verification is bound to the originally prepared amount, accounts, memo, origin,
and ELIS tab. Subframe and other-extension requests are rejected. Preparation
requires approval on an extension-owned page with a one-use request nonce and a
two-minute expiry. Page text is rendered using textContent. Production callers
are disabled; do not deploy this local-only build as a production extension.

Residual risks: Truliant page-modification permission is powerful. A malicious
change to the installed unpacked code or a compromised browser/host can defeat
application-level safeguards. The server's history-match endpoint trusts the
signed-in client and is not independent cryptographic proof of a bank transfer.
The pilot must not be treated as an authoritative accounting feed. No independent
security audit or installed-browser acceptance has been performed.

The tool-driven installation attempt was blocked by browser URL security policy.
The user must install manually using the steps above; no workaround was attempted.
