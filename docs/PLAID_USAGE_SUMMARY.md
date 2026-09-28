# Plaid usage summary

Bank Monitor displays owner-only, integration-wide recorded API attempts for the current UTC month. Counts include all ELIS businesses using this integration and are filtered by PLAID_ENV. The summary endpoint reads the database only; loading or refreshing it does not call Plaid.

New `plaid_api_calls` rows store only timestamp, endpoint, environment and outcome. Web startup creates the additive table; deploy web before worker. Both processes must run the new code with `PLAID_USAGE_TRACKING_ENABLED=true`. No historical calls are reconstructed. A failed telemetry write logs a safe warning and does not cause a successful bank request to be retried.

Set `PLAID_BALANCE_RATE_USD` to the verified contract rate (Elis Pro Tech: 0.10, verified September 28, 2026). The estimate covers recorded successful Balance calls only, before allowances/credits; it excludes subscriptions and other products. Timeout outcomes remain unknown. Official billable usage and invoices are unavailable, never inferred as zero.

`PLAID_TRANSACTIONS_FREE_EXHAUSTED_AT=2026-09-26T14:03:00-04:00` records the user-supplied Plaid notice. It is a dated saved notice, not a live provider allowance balance. Remove/update this setting when verified provider information changes.

Future provider reconciliation can use Plaid Dashboard MCP usage reports. No MCP tokens, account rates fetched live, or official invoice synchronization are implemented in this release. Dashboard usage and billing links remain the authoritative reference.
