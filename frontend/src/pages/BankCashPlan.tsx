export type CashPlan = {
  observed_at: string
  reserve_cents: number
  cash_accounts: {
    last4: string
    nickname: string
    current_cents: number | null
    available_cents: number | null
    availability_difference_cents: number | null
    planning_limit_cents: number | null
    observed_pending_debit_cents: number | null
    observed_pending_count: number | null
    pending_details: { description: string; amount_cents: number; date?: string | null }[]
    pending_details_truncated: boolean
  }[]
  checking_routes: { from_last4: string; to_last4: string; amount_cents: number }[]
  credit_routes: { from_last4: string; to_last4: string; amount_cents: number; payoff_unverified: boolean }[]
  transaction_feed_status: string
  last_transaction_update: string | null
}

const money = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })

type CreditAccount = { last4: string; nickname: string; balance?: { available_credit_cents: number | null; outstanding_cents?: number | null } }

export default function BankCashPlan({ plan, creditAccounts, balanceObservedAt, providerAccountLast4, repaymentEnabled, onReviewRepayment }: { plan: CashPlan; creditAccounts: CreditAccount[]; balanceObservedAt: string | null; providerAccountLast4: string[]; repaymentEnabled: boolean; onReviewRepayment: () => void }) {
  const cashNames = Object.fromEntries(plan.cash_accounts.map(account => [account.last4, account.nickname]))
  const creditNames = Object.fromEntries(creditAccounts.map(account => [account.last4, account.nickname]))
  const feedAvailable = plan.transaction_feed_status === 'observed'
  const newerBalanceRead = Boolean(balanceObservedAt && Date.parse(balanceObservedAt) > Date.parse(plan.observed_at))
  const missingCredit = creditAccounts.filter(account => !providerAccountLast4.includes(account.last4))
  return <section aria-labelledby="cash-plan-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="border-b border-slate-200 p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Account overview</p>
      <h2 id="cash-plan-title" className="mt-1 text-xl font-semibold text-slate-950">Cash, credit and possible transfers</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">Plaid cash snapshot from {new Date(plan.observed_at).toLocaleString()}. The planning limit uses the lower of posted and bank-available cash, then protects {money(plan.reserve_cents)} per checking account. It is a review ceiling, not a transfer approval.</p>
    </div>
    {(newerBalanceRead || missingCredit.length > 0) && <div role="status" className="mx-5 mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950 sm:mx-6">{newerBalanceRead && <p>A newer bank balance read exists. Refresh Plaid to update these planning figures.</p>}{missingCredit.length > 0 && <p>Plaid did not return {missingCredit.map(account => `••${account.last4}`).join(', ')} in this read. Its payoff and transfer options are not included below; review the bank connection before relying on this plan.</p>}</div>}
    <div className="grid gap-6 px-5 pt-5 sm:px-6 sm:pt-6 xl:grid-cols-2">
      <section aria-labelledby="cash-account-heading"><h3 id="cash-account-heading" className="font-semibold text-slate-950">Checking cash <span className="ml-2 text-xs font-normal text-slate-500">Potential sources</span></h3>
    <div className="grid gap-4 py-4 2xl:grid-cols-2">
      {plan.cash_accounts.map(account => <article key={account.last4} className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
        <div className="flex items-start justify-between gap-3"><h3 className="font-semibold text-slate-950">{account.nickname}</h3><span className="shrink-0 text-sm text-slate-500">••{account.last4}</span></div>
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div><dt className="text-slate-500">Posted</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{account.current_cents == null ? 'Unavailable' : money(account.current_cents)}</dd></div>
          <div><dt className="text-slate-500">Bank available</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{account.available_cents == null ? 'Unavailable' : money(account.available_cents)}</dd></div>
          <div><dt className="text-slate-500">Planning limit</dt><dd className="mt-1 font-semibold tabular-nums text-blue-700">{account.planning_limit_cents == null ? 'Cannot calculate' : money(account.planning_limit_cents)}</dd></div>
          <div><dt className="text-slate-500">Pending reported</dt><dd className="mt-1 font-semibold tabular-nums text-amber-800">{!feedAvailable || account.observed_pending_debit_cents == null ? 'Unverified' : `${money(account.observed_pending_debit_cents)} · ${account.observed_pending_count ?? 0}`}</dd></div>
        </dl>
        {account.availability_difference_cents != null && account.availability_difference_cents > 0 && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">Bank available is {money(account.availability_difference_cents)} below posted. This difference may include holds or other bank adjustments; it is not an itemized pending-debit total.</p>}
        {feedAvailable && account.pending_details.length > 0 && <details className="mt-4 border-t border-slate-100 pt-3"><summary className="cursor-pointer text-sm font-semibold text-blue-700">View reported pending entries</summary><ul className="mt-3 space-y-2 text-sm">{account.pending_details.map((entry, index) => <li key={`${entry.date}-${entry.description}-${index}`} className="flex justify-between gap-3"><span className="min-w-0 truncate text-slate-700">{entry.description}{entry.date ? ` · ${entry.date}` : ''}</span><span className="shrink-0 font-medium tabular-nums text-slate-900">{money(entry.amount_cents)}</span></li>)}</ul>{account.pending_details_truncated && <p className="mt-2 text-xs text-amber-800">Only the newest 30 entries are displayed; the total includes all reported entries.</p>}</details>}
      </article>)}
    </div></section>
      <section aria-labelledby="credit-account-heading"><h3 id="credit-account-heading" className="font-semibold text-slate-950">Credit accounts <span className="ml-2 text-xs font-normal text-slate-500">Possible destinations</span></h3><div className="grid gap-4 py-4 2xl:grid-cols-2">{creditAccounts.map(account => <article key={account.last4} className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4"><div className="flex justify-between gap-2"><span className="text-xs font-semibold uppercase tracking-wide text-blue-800">Credit</span><span className="text-xs tabular-nums text-blue-800">••{account.last4}</span></div><h4 className="mt-3 min-h-10 text-sm font-semibold leading-5 text-slate-950">{account.nickname}</h4><p className="mt-2 text-2xl font-semibold tabular-nums text-slate-950">{account.balance?.available_credit_cents == null ? 'Unavailable' : money(account.balance.available_credit_cents)}</p><p className="text-xs text-slate-600">Available credit, not payoff</p><div className="mt-4 flex justify-between gap-2 border-t border-blue-200 pt-3 text-xs"><span className="text-slate-600">Full payoff</span><span className="font-medium text-amber-900">{account.balance?.outstanding_cents == null ? 'Needs verification' : money(account.balance.outstanding_cents)}</span></div>{!providerAccountLast4.includes(account.last4) && <p className="mt-3 text-xs font-medium text-amber-900">Missing from Plaid read</p>}</article>)}</div></section>
    </div>
    <div className="mx-5 mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950 sm:mx-6 sm:mb-6">{feedAvailable ? 'Plaid may omit pending transactions even when none appear here.' : 'Plaid transaction details were unavailable in this read.'} Bank-available cash may already reflect holds, so reported pending debits are not subtracted again. {plan.last_transaction_update ? `Last transaction-feed update: ${new Date(plan.last_transaction_update).toLocaleString()}.` : 'Transaction-feed freshness is unknown.'}</div>
    <div className="border-t border-slate-200 p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Planning only</p><h3 className="mt-1 text-lg font-semibold text-slate-950">Routes to review</h3><p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">ELIS allocates cash in order: checking shortfalls first, then credit accounts in your repayment priority. These are balance-based ceilings, not approved transfer amounts.</p></div><button type="button" disabled={!repaymentEnabled} onClick={onReviewRepayment} className="min-h-11 shrink-0 rounded-xl bg-blue-700 px-4 font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50">Review repayment for form prep</button></div>
      {!repaymentEnabled && <p className="mt-2 text-xs text-amber-900">Enable Friday repayment in monitoring settings to prepare a credit repayment form.</p>}
      {plan.checking_routes.length === 0 && plan.credit_routes.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No balance-based route is available with the current account balances and reserve.</p> : <div className="mt-4 space-y-2">
        {plan.checking_routes.map((route, index) => <div key={`checking-${index}`} className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><span className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Step {index + 1} · Checking coverage</span><strong className="tabular-nums text-emerald-950">Up to {money(route.amount_cents)}</strong></div><p className="mt-2 font-medium text-emerald-950">From checking {cashNames[route.from_last4] || 'account'} · ••{route.from_last4}</p><p className="text-emerald-950">To checking {cashNames[route.to_last4] || 'account'} · ••{route.to_last4}</p><p className="mt-2 text-xs text-amber-900">Requires a separate checking-transfer review before form preparation.</p></div>)}
        {plan.credit_routes.map((route, index) => <div key={`credit-${index}`} className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><span className="text-xs font-semibold uppercase tracking-wide text-blue-800">Step {plan.checking_routes.length + index + 1} · Credit repayment</span><strong className="tabular-nums text-blue-950">Up to {money(route.amount_cents)}</strong></div><p className="mt-2 font-medium text-blue-950">From checking {cashNames[route.from_last4] || 'account'} · ••{route.from_last4}</p><p className="text-blue-950">To credit {creditNames[route.to_last4] || 'account'} · ••{route.to_last4}</p><p className="mt-2 text-xs text-amber-900">Pending debits, usable cash and full payoff need verification.</p></div>)}
      </div>}
      <p className="mt-4 text-xs leading-5 text-slate-500">Review the exact figures, add the resulting proposal to the queue, then let ELIS prepare the Truliant form. You sign in and submit the transfer yourself.</p>
    </div>
  </section>
}
