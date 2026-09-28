# Plaid usage summary

Bank Monitor displays owner-only, integration-wide recorded API attempts for the current UTC month. Counts include all ELIS businesses using this integration and are filtered by PLAID_ENV. The summary endpoint reads the database only; loading or refreshing it does not call Plaid.

New `plaid_api_calls` rows store only timestamp, endpoint, environment and outcome. Web startup creates the additive table; deploy web before worker. Both processes must run the new code with `PLAID_USAGE_TRACKING_ENABLED=true`. No historical calls are reconstructed. A failed telemetry write logs a safe warning and does not cause a successful bank request to be retried.

Set `PLAID_BALANCE_RATE_USD` to the verified contract rate (Elis Pro Tech: 0.10, verified September 28, 2026). The estimate covers recorded successful Balance calls only, before allowances/credits; it excludes subscriptions and other products. Timeout outcomes remain unknown. Official billable usage and invoices are unavailable, never inferred as zero.

`PLAID_TRANSACTIONS_FREE_EXHAUSTED_AT=2026-09-26T14:03:00-04:00` records the user-supplied Plaid notice. It is a dated saved notice, not a live provider allowance balance. Remove/update this setting when verified provider information changes.

Future provider reconciliation can use Plaid Dashboard MCP usage reports. No MCP tokens, account rates fetched live, or official invoice synchronization are implemented in this release. Dashboard usage and billing links remain the authoritative reference.

## Allowance view (September 28 revision)

The panel is last in the Bank Monitor overview and collapsed by default. Opening it loads ELIS request counts and a read-only Plaid Dashboard MCP report. The backend uses the existing Production credentials to acquire a short-lived Dashboard token; it is never returned to the frontend, persisted, or logged. `PLAID_DASHBOARD_TEAM_ID` pins the report to the verified Elis Pro Tech team. Production-only reports are cached per process/team/month for one hour (failures for one minute). No bank data endpoint is called by these reads.

`PLAID_ALLOWANCE_SNAPSHOT` supplies a dated, manually verified Products-page snapshot and contracted rates. These bars are explicitly **saved, not live**. Dashboard MCP exposes usage series, not the Products-page free allowance counters. The September 28 query returned empty observations for Balance, Transactions, Liabilities, and Transactions Refresh; absence of observations is not treated as a zero invoice. The frontend does not calculate a subscription bill from API call counts. Live allowances and invoices remain accessible through direct Dashboard links.

Observed Products counters: Balance 79/200, Liabilities 76/200, Identity 53/200. Transactions exhaustion is supported by the September 26 Plaid email; its denominator is not invented. Snapshot values are not advanced by local request counters because that would conflate partial telemetry with provider allowance accounting. Local activity remains forward-only and clearly dated.
