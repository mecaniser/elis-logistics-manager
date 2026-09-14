# Targeted bank extension security review — 2026-09-14

The local pilot received targeted hardening, not an independent security
certification. Installation and Chrome runtime acceptance remain unverified.

## Findings fixed

1. **High: verification request not bound to prepared details.** A caller on an
   allowed origin could change accounts, memo or amount while retaining a draft ID.
   `browser-extension/elis-bank-assistant/contract.js:15` now binds those fields,
   origin and ELIS tab; background verification enforces it before bank access.
2. **Medium: shared development/production caller trust.** Local code and production
   could both invoke one extension. `contract.js:6` and `manifest.json` now permit
   only the local pilot. Production is not enabled.
3. **High: allowed-page compromise could initiate form filling.** Preparation now
   requires a review on an extension-owned page, authenticated by extension ID,
   exact tab/URL and one-use nonce, with expiry. See `background.js:72` and
   `background.js:84`. It never approves the bank transfer itself.

## Residual risks and rollout limits

4. **High-impact capability remains:** the manifest grants scripting access to
   authenticated Truliant pages. No browser permission enforces fill-only behavior.
   Malicious modification of local extension files, browser compromise, or a
   compromised host remains a risk. No submit action exists in the reviewed code.
5. **Medium: completion evidence is client-reported.**
   `backend/app/routers/bank_monitor.py:150` accepts hashes from the authenticated
   application principal. A compromised authenticated client could forge a matched
   status. The label identifies browser-reported matching; it must not become an
   independent accounting or payment authorization signal. No bank API attestation
   exists. Strong independent verification is a production requirement.
6. **Availability/recovery:** Chrome restarts, changed bank markup, lost tabs and
   expired sessions can leave drafts locked. General production rollout is blocked
   until safe reconciliation/recovery and actual browser acceptance are completed.

## Validation

Eleven simulated extension tests pass, including rejected origins, altered draft
fields, changed tab, insufficient whole-charge credit, existing forms, ambiguous
history and wrong-sign entries. These are not live bank execution tests. CSP and
extension-owned approval behavior still require Chrome installation acceptance.
No credentials were collected and no transfer was submitted during this review.

Chrome installation was attempted after user approval. The browser tool blocked
chrome://extensions under URL security policy and explicitly disallowed alternate
routes. No bypass was attempted. The user must manually install the local package.

Primary reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging
