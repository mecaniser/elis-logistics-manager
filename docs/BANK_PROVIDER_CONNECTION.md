# Consented provider connection for Bank Monitor

This implementation adds a Plaid Link connection and server-side read path. It is
disabled until explicitly configured. It does not accept a Truliant password,
store bank cookies, initiate a payment, or submit a transfer.

## Provisioning and rollout

1. Obtain a Plaid **Production** account with Truliant access, Transactions and
   Balance entitlements, and confirm in Plaid's live institution API that the
   configured checking and credit accounts are available. The public coverage
   file is only a candidate signal, not proof of current eligibility, account
   coverage, or an OAuth/FDX connection.
2. Register an HTTPS `PLAID_REDIRECT_URI` in the Plaid Dashboard that returns to
   the Bank Monitor page with no query parameters. Set that exact URI, plus
   `PLAID_ENV=production`, `PLAID_CLIENT_ID`, `PLAID_SECRET`, and a stable
   Fernet key in `BANK_MONITOR_TOKEN_KEY` on both web and bank worker services.
   Generate the key with `Fernet.generate_key()` in a trusted environment. Do
   not print or commit production secrets. Keep the same key across deploys;
   rotation requires re-encrypting saved tokens.
3. Deploy the web service first so the new tables are created, then the worker.
   Keep the existing reader mode while provisioning production credentials.
4. In Bank Monitor, connect Truliant through Plaid Link **before cutover**. The
   server checks the institution ID, binds every configured four-digit suffix
   to one exact account, and validates the current balance response. Existing
   Chrome checks continue during this setup.
5. Set `BANK_MONITOR_READER_MODE=plaid` on **both** services for a supervised
   cutover. Use **Verify server bank read** and inspect the status and account
   count before relying on scheduled checks. Observe a completed daily run as
   separate evidence. Renew access through Plaid Link when the bank requires
   reauthorization. No saved browser session is involved.

Balance reads use Plaid `/accounts/balance/get`. The worker checks the Item and
each mapped account before recording balances. A missing account, credit
availability, provider error, or reauthorization request blocks the run. This
implementation does not interpret a cached transaction feed as proof of zero
pending debits. With `posted_and_pending`, it records balances but withholds
coverage and repayment proposals. `posted` can produce a coverage proposal from
a complete current balance read. Friday repayment remains blocked unless all
cash, income, pending-debit, and payoff evidence is verified by an appropriate
source or manually entered in the existing on-demand flow.

Provider access can end or require renewed user consent. An initial successful
link is not evidence of uninterrupted future access. The scheduled worker is
still responsible for reporting actual check outcomes. Do not describe this as
fully unattended until a production consent, server read, and scheduled run are
observed, and separately confirm how Truliant renews access for this Item.
