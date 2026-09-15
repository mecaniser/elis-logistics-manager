# ELIS Bank Monitor QA Report

- Date: 2026-09-14
- Scope: Chrome extension approval, reload recovery, two-account posted-history verification, evidence acknowledgement, and ELIS version gate
- Candidate: 0.1.10
- Environment: local ELIS preview at `http://127.0.0.1:18081/bank-monitor`; deterministic Truliant frame fixtures; no bank transfer was created or submitted during QA
- Status: automated acceptance passed; live browser acceptance pending one Chrome extension reload

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
- Fix status: verified in deterministic regression; final live rerun pending
- Commit: `ad04062`
- Regression: `b72533c`
- Files: `browser-extension/elis-bank-assistant/bank-history-content.js`, `browser-extension/elis-bank-assistant/tests/navigation-response.regression-1.test.js`

## Verification

- Extension: 23/23 tests passed, including the complete verification state machine, stage failures, and browser navigation response ordering.
- Backend: 36/36 targeted bank-monitor tests passed.
- Frontend: TypeScript and Vite production build passed.
- Browser: local ELIS page loaded the rebuilt bundle and correctly blocked installed extension 0.1.8, requiring candidate 0.1.9.
- Safety: verification tests assert that the read-only path never invokes transfer-form scripting or submission.

## Remaining acceptance gate

Chrome security requires the user to reload unpacked extension 0.1.10. After that, ELIS must report 0.1.10, the user must approve the extension-owned read-only verification page, and the live flow must find the already-posted $118.20 deposit in checking 3304 and disbursement in source 2829. ELIS must then show `bank_history_matched`. No further source change is justified unless this single live run produces new evidence.

QA found 3 issues, fixed 3, automated flow confidence 35 -> 92. Live bank acceptance remains the release gate.
