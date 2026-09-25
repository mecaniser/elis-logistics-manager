# Consented provider connection for Bank Monitor

This implementation adds a Plaid Link connection and server-side read path. It is
disabled until explicitly configured. It does not accept a Truliant password,
store bank cookies, initiate a payment, or submit a transfer.

## Provisioning and rollout

1. Obtain a Plaid **Production** account with Truliant access, Transactions,
   Liabilities, and Balance entitlements, and confirm in Plaid's live institution API that the
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
5. While `BANK_MONITOR_READER_MODE=signed_in_chrome`, a linked Item can be
   checked with **Check server data now**. At 5:30 p.m. Eastern, the worker
   records a read-only Plaid balance observation even when Chrome is closed.
   If the Chrome assistant completes a fuller bank-history check before 5:45,
   that check replaces the same day's provisional Plaid result. No server-side
   Truliant browser or saved bank password is used.
6. A later supervised cutover to `BANK_MONITOR_READER_MODE=plaid` on **both**
   services requires separate evidence that the resulting proposals meet the
   configured rule. Renew access through Plaid Link when the bank requires
   reauthorization.

Balance reads use Plaid `/accounts/balance/get`. The worker checks the Item and
each mapped account before recording balances. A missing account, provider error,
or reauthorization request blocks the run; a missing individual balance is
shown as unavailable and blocks automatic proposals. The cash view displays
posted and bank-available balances, a conservative per-account planning limit,
and the pending debits actually reported by Plaid. Available cash may already
reflect holds, so reported pending debits are not subtracted again. The view
can show planning ceilings between checking accounts and toward credit lines,
but these are not payment instructions or verified payoff amounts. The feed
does **not** treat a zero count, or a nonzero count, as proof that every pending
debit is present. With `posted_and_pending`, it records balances but withholds
coverage and repayment proposals. `posted` can produce a coverage proposal from
a complete current balance read. Friday repayment remains blocked unless all
cash, income, pending-debit, and payoff evidence is verified by an appropriate
source or manually entered in the existing on-demand flow.

The main refresh action uses Plaid when a consented connection exists. Chrome
remains a separate detailed bank-history and transfer-preparation path. A
prepared transfer may be reconciled from Plaid only after a unique posted debit
and credit pair is displayed and explicitly confirmed; feed gaps or ambiguous
entries keep it open. The current Link Item covers one Truliant institution
connection. Additional accounts already consented in that Item can be discovered
and added in settings. Other banks, duplicate last-four-digit suffixes, and
payments submitted through the bank are outside this reader's current scope.

The first production observation on September 25, 2026 found four mapped
accounts and zero pending entries in Plaid's feed. A contemporaneous Chrome
read also found no pending debit in either checking account, so this does not
establish whether Truliant supplies pending transactions when one exists.
Compare an actual pending debit visible in Truliant with a Plaid read before
using that feed for any pending-charge workflow. Even a successful match is
evidence of that item, not a guarantee of completeness for all future items.

Provider access can end or require renewed user consent. An initial successful
link is not evidence of uninterrupted future access. The scheduled worker is
still responsible for reporting actual check outcomes. Do not describe this as
fully unattended until a production consent, server read, and scheduled run are
observed, and separately confirm how Truliant renews access for this Item.
