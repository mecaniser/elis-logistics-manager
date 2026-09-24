# ELIS Bank Monitor QA Report

- Date: 2026-09-14
- Scope: Chrome extension approval, reload recovery, two-account posted-history verification, evidence acknowledgement, and ELIS version gate
- Candidate: 0.1.12
- Environment: local ELIS preview at `http://127.0.0.1:18081/bank-monitor`; deterministic Truliant frame fixtures; no bank transfer was created or submitted during QA
- Status: automated and live browser acceptance passed

## Outcome

QA found 3 high-severity sequencing bugs and fixed all three. The deterministic suite now drives reauthorization, destination checking selection and deposit match, funding-source selection and disbursement match, separate evidence creation, matched-state persistence, and final ELIS acknowledgement. It also covers delayed account cards, empty frames, unrelated frames, navigation response order, duplicate responsive headings, exact date/amount/memo/type matching, and failures at destination/source stages.

## ISSUE-001: Valid verification rejected immediately after approval

- Severity: High
- Category: Functional
- Trigger: ELIS sends `ELIS_VERIFY` immediately after `ELIS_REAUTHORIZE_VERIFY` resolves.
- Before: the extension replied before clearing its `busy` flag, so the next valid request returned `Another form is being prepared.`
- Fix: clear the lifecycle lock before resolving the external response.
- Fix status: verified
- Commit: `7503f3a`
- Regression: `f91d11a`
- Files: `browser-extension/elis-bank-assistant/background.js`, `browser-extension/elis-bank-assistant/tests/acceptance.test.js`
- Before: [issue-001-before.png](screenshots/issue-001-before.png)
- After: [issue-001-after.png](screenshots/issue-001-after.png)

## ISSUE-002: Unrelated Truliant frame could win account-selection response

- Severity: High
- Category: Functional
- Trigger: a child frame has account-link elements but not the requested account, while the actual account frame renders later.
- Before: the unrelated frame replied `{opened:false}` and could win Chrome's tab-wide message response.
- Fix: frames without the exact requested suffix remain silent; only the requested account frame responds.
- Fix status: verified
- Commit: `d8bafd2`
- Regression: `81abd83`
- Files: `browser-extension/elis-bank-assistant/bank-history-content.js`, `browser-extension/elis-bank-assistant/tests/frame-acceptance.regression-1.test.js`

## ISSUE-003: Account navigation destroyed the success reply

- Severity: High
- Category: Functional
- Trigger: clicking account 3304 navigates the child frame before Chrome delivers its response to the service worker.
- Before: Truliant reached account history, but ELIS timed out and reported that the account could not be opened.
- Fix: deliver the success response first, then schedule navigation in the next task.
- Fix status: verified in deterministic regression and live bank run
- Commit: `ad04062`
- Regression: `b72533c`
- Files: `browser-extension/elis-bank-assistant/bank-history-content.js`, `browser-extension/elis-bank-assistant/tests/navigation-response.regression-1.test.js`

## Verification

- Extension: 23/23 tests passed, including the complete verification state machine, stage failures, and browser navigation response ordering.
- Backend: 36/36 targeted bank-monitor tests passed.
- Frontend: TypeScript and Vite production build passed.
- Browser: local ELIS page enforced exact extension versions through the acceptance sequence and completed successfully on 0.1.12.
- Safety: verification tests assert that the read-only path never invokes transfer-form scripting or submission.

## Live acceptance result

Extension 0.1.12 found the already-posted $118.20 deposit in checking 3304 and the matching principal disbursement in source 2829. ELIS persisted `bank_history_matched` with two separate 64-character evidence hashes. No transfer was created or submitted during verification. See [live-acceptance-0.1.12.png](screenshots/live-acceptance-0.1.12.png).

QA found 4 issues, fixed 4, and completed the live bank acceptance gate.
