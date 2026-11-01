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

The worker performs one complete authenticated source reconciliation on startup
(including outside shop hours), then hourly only on configured open days from
09:00 through 19:00 inclusive, in `America/New_York`. The 19:00 check is a
closing check: eleven backup slots per open day. ZoneInfo handles DST. The
opening check recovers missing events from overnight, weekends and closures;
there is no source date filter that could discard that history. A delayed worker
runs only the latest due slot, not a burst of every missed hour. Failed passes
roll back and recover at the next backup or restart.

`ELIS_DIESELBRIDGE_BACKUP_SCHEDULE` is a bounded JSON setting. Example for a
Monday–Friday shop (illustrative; actual shop days require confirmation):

```json
{"timezone":"America/New_York","open_hour":9,"close_hour":19,"interval_hours":1,"weekdays":[0,1,2,3,4],"closed_dates":[]}
```

Weekdays use Monday=0, Sunday=6. Configurable hours are integer 0–23 with opening
before closing; interval is 1–12 hours. At most 366 ISO closure dates are allowed.
Unknown keys or invalid values fail enabled-worker startup. The code default is
all seven days, not an assertion that the shop opens every day. Confirm and set
actual days before activation. The final closing slot is retained for intervals
that do not divide the window evenly. Restart applies schedule changes.

Signed webhook notifications wake EDG promptly at any hour, including closed
days. Verification and inbox commit precede the in-process wakeup. PostgreSQL
transactional NOTIFY also wakes other worker processes; its payload is empty.
A dedicated LISTEN socket uses no idle SQL polling. Listener startup/reconnect
first subscribes then drains durable jobs, closing the reconnect race. Listener
failure retries the connection after 60 seconds; source backup remains the
independent recovery path. SQLite development uses the in-process wakeup only.
One extra PostgreSQL connection per enabled web worker is required.

The worker sleeps until a committed event, persisted retry/lease deadline, backup
slot or shutdown. There is no two-second idle inbox query. An inbox job is leased
briefly, fetched outside database/tenant locks, then applied and acknowledged in
one transaction. Expired two-minute leases are reclaimable; an attempt/expiry
fence prevents a stale worker from applying. Tenant locking and durable operation
keys serialize financial writes across replicas. Catch-up also fetches before
taking the tenant finance lock and rechecks local scope/idempotency under lock.

New eligible finalized invoices create ordinary repair tiles and cost/payable
entries against uniquely identified equipment. Changed, cancelled, inaccessible,
ambiguous-equipment or otherwise unsafe records remain review work. Catch-up
never infers payment or writes a reserve withdrawal. Verified payment facts still
require the established payment workflow; no new automatic payment posting is
introduced. Existing receipts are preserved. No schema migration is required.

DBN's existing delivery dispatcher still checks its outbox every ten seconds
when enabled (no HTTP for an empty outbox). This PR changes EDG inbox behavior,
not DBN's dispatcher cadence. Delivery times remain subject to queue/network
health; notifications are wakeups and the scoped source API remains authoritative.
Each event currently fetches a full manifest, then selects the notified order.
The source API has no incremental filter, cursor or ETag; no PDF is downloaded.

### Measured resource baseline

One read-only production observation for 15 unchanged orders: one source GET,
36,508 decoded bytes / 8,462 transferred bytes, 0.082 seconds elapsed, and 92 EDG
SQL statements for the pure preview alone. This is not the full importing-pass
SQL count or a latency guarantee. Source construction uses one joined snapshot
query plus authentication/scope reads. A first unchanged catch-up may preserve
15 missing immutable observation-evidence rows and an operation audit record;
it must not create payments or costs again.

The previous inactive five-minute schedule implied 288 full GETs/day, plus
43,200 idle inbox checks/day per web replica. The new configuration uses eleven
backup GETs per open day/connection/replica, plus one per startup and actual
events/retries. Durable keys prevent duplicate financial effects, not every
redundant remote GET across replicas. The synthetic idle-worker test observes
one drain/deadline lookup then one timed sleep, rather than repeated SQL.
No per-call fee appears in application code; infrastructure dollar cost was not
measured and is not claimed to be zero.

## Activation is a separate approved operation

This change does not enable flags, configure destinations or create credentials.
Current inspected state: EDG financial/worker/historical-cash flags off; no EDG
webhook verifier; DBN delivery off with no destination for this customer.

After release approval and deployment:

1. Refresh the full source preview and verify the 15 reconciled records remain
   unchanged, with their payments and reserves intact. Review any newly eligible
   invoices before activating unattended imports.
2. Confirm actual open weekdays/closure dates and configure the backup schedule.
   For authenticated pull, explicitly authorize enabling both
   `ELIS_DIESELBRIDGE_FINANCIAL_ENABLED` and
   `ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED` and restarting EDG. Verify the
   initial `startup:v2:` operation, resulting tiles and no new payment effects.
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
