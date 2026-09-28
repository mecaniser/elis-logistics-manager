# Coverage proposals

Scheduled profile checks persist coverage suggestions in `last_evaluation`; profile GET also derives them from the last stored balances so today's existing check can surface immediately without replaying a provider read. The browser polls that database view every minute while visible. It does not call Plaid while polling.

For each canonical checking account, the lower coverage amount is reserve minus the lesser of posted and available balances, less unfinished incoming drafts. The upper amount also considers posted minus reported pending debits. These are bounded review scenarios, not proof that a pending debit is additional. When they differ, the amount input starts blank and the user must reconcile it against the bank. Unknown pending data also requires review. Explicit same-account posted `pending_transaction_id` references remove replaced pending entries; equal amounts alone never prove duplication.

Enabled funding routes are allocated in saved priority order, bounded by source availability, reserves, and unfinished outgoing drafts. Proposals share source capacity within a profile; draft creation serializes by tenant and deducts incoming/outgoing drafts across canonical identities and legacy suffixes. Unfunded needs remain visible.

Opening a review refreshes the bank profile and recomputes coverage. The existing five-minute freshness, route, currency, identity, source-capacity and duplicate checks remain. Coverage draft creation additionally requires explicit confirmation and bounds the amount by both reviewed and current coverage need. Approval and amount are retained in the review record. The scheduler never creates an approved draft or submits a transfer. User submission remains in Truliant.

Validation: 135 banking/Plaid tests, frontend build, targeted ESLint, diff checks. Regression cases include -$340 with $636.86 ambiguous pending, pending already reflected in available cash, explicit pending-to-posted replacement, stale review, concurrent incoming drafts, and one daily proposal run without transfer creation.
