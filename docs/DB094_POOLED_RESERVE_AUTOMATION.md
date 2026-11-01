# Shared repair reserve and automatic invoice catch-up

## Shared management fund

The company repair reserve is one management fund across all equipment. The
existing Business funds calculation remains the source of truth. The new
read-only `/api/repair-reserve-pool` endpoint reuses that calculation: original
settlement contributions, legacy saved reserve spending, verified DBN payments
and their reversals, and adjustments. Derived trailer settlement copies and
synced ledger copies do not add the same funds twice. Negative company balances
remain supported. Bank cash coverage is a separate reconciliation.

Vehicle and invoice review pages show the shared fund. Equipment pages retain
contributions, usage, adjustments and the net contribution minus usage for cost
attribution. An equipment-level negative net is not a separate spending limit.
Repair attribution, journals, invoices and all existing ledger rows are retained;
there is no transfer of historical spending between equipment.

The generic canonical Finance `reserve` command still supports earmarked
reservations per earning pair. That separate accounting API is unchanged. It
must not be treated as the company management fund or silently populated from
this display. The production inspection found zero such active reservations.

## Initial and periodic reconciliation

The financial worker runs a complete source reconciliation immediately on startup
and every five minutes, including when notifications are continuously queued.
Each pass uses the existing authenticated, tenant/customer-scoped financial
manifest and importer. Missing wakeups and invoices finalized before webhook
setup are therefore recovered. A separate transaction per connection isolates
failures. The existing tenant lock and a durable five-minute-bucket operation key
serialize replicas, restarts and concurrent webhook jobs.

New eligible finalized invoices create ordinary repair tiles and cost/payable
entries against uniquely identified equipment. Changed, cancelled, inaccessible,
ambiguous-equipment or otherwise unsafe records remain review work. Catch-up
never infers payment or writes a reserve withdrawal. Existing verified receipts
are preserved and are not re-imported as new payments. Failed passes roll back;
subsequent scheduled passes retry. Logs expose only safe error codes. No new
schema migration is required.

Signed webhook notifications remain the faster wakeup path: DBN delivery is
scheduled every ten seconds and EDG checks its inbox every two seconds. These
are scheduling cadences, not guaranteed delivery times. The five-minute source
refetch is the independent backstop. Authenticated pull does not need a webhook
signing secret; the existing scoped read key remains authoritative. Invalid or
unsigned pushes still cannot enter the event inbox.

## Activation is a separate approved operation

This change does not enable flags, configure destinations or create credentials.
Current inspected state: EDG financial/worker/historical-cash flags off; no EDG
webhook verifier; DBN delivery off with no destination for this customer.

After release approval and deployment:

1. Refresh the full source preview and verify the 15 reconciled records remain
   unchanged, with their payments and reserves intact. Review any newly eligible
   invoices before activating unattended imports.
2. For authenticated pull, explicitly authorize enabling both
   `ELIS_DIESELBRIDGE_FINANCIAL_ENABLED` and
   `ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED` and restarting EDG. Verify the
   initial `catchup:v1:` operation, resulting tiles and no new payment effects.
3. For faster signed delivery, separately approve one independent signing secret
   shared only between the scoped DBN sender and EDG verifier. Add EDG connection
   `event_secret_env` and DBN `DIESELBRIDGE_FLEET_WEBHOOKS` for Truck Pit Stop →
   Elis Logistics, destination
   `https://www.elisprotech.com/api/v1/accounting/dieselbridge/webhooks/truck-pit-stop`.
   Do not reuse or broaden the existing invoice read key. Keep secret values out
   of logs, PRs and chat. Verify signatures, scoped replay, and review behavior,
   then explicitly enable DBN delivery and verify its scheduler/worker health.
4. Monitor source/refetch failures and review queues. Repeating a successful pass
   must create no duplicate costs or payments. Keep
   `ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED` off; it is unrelated to invoice sync.

Turning off the EDG worker flag stops unattended processing after service restart;
turning off financial enablement also rejects financial writes. Neither rollback
step removes imported history. Correct financial records only through the existing
reviewed correction and reversal workflows.
