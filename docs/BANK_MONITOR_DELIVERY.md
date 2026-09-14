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
