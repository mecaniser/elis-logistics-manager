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

export default function BankCashPlan({ plan, creditNames }: { plan: CashPlan; creditNames: Record<string, string> }) {
  const cashNames = Object.fromEntries(plan.cash_accounts.map(account => [account.last4, account.nickname]))
  const feedAvailable = plan.transaction_feed_status === 'observed'
  return <section aria-labelledby="cash-plan-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="border-b border-slate-200 p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Plaid cash view</p>
      <h2 id="cash-plan-title" className="mt-1 text-xl font-semibold text-slate-950">Cash and transfer possibilities</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">Balance read at {new Date(plan.observed_at).toLocaleString()}. The planning limit uses the lower of posted and bank-available cash, then protects {money(plan.reserve_cents)} per checking account. It is a review ceiling, not a transfer approval.</p>
    </div>
    <div className="grid gap-4 p-5 sm:p-6 lg:grid-cols-2">
      {plan.cash_accounts.map(account => <article key={account.last4} className="rounded-2xl border border-slate-200 p-4">
        <div className="flex items-start justify-between gap-3"><h3 className="font-semibold text-slate-950">{account.nickname}</h3><span className="shrink-0 text-sm text-slate-500">••{account.last4}</span></div>
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div><dt className="text-slate-500">Posted</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{account.current_cents == null ? 'Unavailable' : money(account.current_cents)}</dd></div>
          <div><dt className="text-slate-500">Bank available</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{account.available_cents == null ? 'Unavailable' : money(account.available_cents)}</dd></div>
          <div><dt className="text-slate-500">Planning limit</dt><dd className="mt-1 font-semibold tabular-nums text-blue-700">{account.planning_limit_cents == null ? 'Cannot calculate' : money(account.planning_limit_cents)}</dd></div>
          <div><dt className="text-slate-500">Pending debits reported</dt><dd className="mt-1 font-semibold tabular-nums text-amber-800">{!feedAvailable || account.observed_pending_debit_cents == null ? 'Unavailable' : `${money(account.observed_pending_debit_cents)} · ${account.observed_pending_count ?? 0}`}</dd></div>
        </dl>
        {account.availability_difference_cents != null && account.availability_difference_cents > 0 && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">Bank available is {money(account.availability_difference_cents)} below posted. This difference may include holds or other bank adjustments; it is not an itemized pending-debit total.</p>}
        {feedAvailable && account.pending_details.length > 0 && <details className="mt-4 border-t border-slate-100 pt-3"><summary className="cursor-pointer text-sm font-semibold text-blue-700">View reported pending entries</summary><ul className="mt-3 space-y-2 text-sm">{account.pending_details.map((entry, index) => <li key={`${entry.date}-${entry.description}-${index}`} className="flex justify-between gap-3"><span className="min-w-0 truncate text-slate-700">{entry.description}{entry.date ? ` · ${entry.date}` : ''}</span><span className="shrink-0 font-medium tabular-nums text-slate-900">{money(entry.amount_cents)}</span></li>)}</ul>{account.pending_details_truncated && <p className="mt-2 text-xs text-amber-800">Only the newest 30 entries are displayed; the total includes all reported entries.</p>}</details>}
      </article>)}
    </div>
    <div className="mx-5 mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950 sm:mx-6 sm:mb-6">{feedAvailable ? 'Plaid may omit pending transactions even when none appear here.' : 'Plaid transaction details were unavailable in this read.'} Bank-available cash may already reflect holds, so reported pending debits are not subtracted again. {plan.last_transaction_update ? `Last transaction-feed update: ${new Date(plan.last_transaction_update).toLocaleString()}.` : 'Transaction-feed freshness is unknown.'}</div>
    <div className="border-t border-slate-200 p-5 sm:p-6">
      <h3 className="font-semibold text-slate-950">Potential routes to review</h3>
      <p className="mt-1 text-sm leading-6 text-slate-600">Amounts below are balance-based ceilings across all configured accounts. ELIS has not verified every pending debit or the exact credit-line payoff, and has not moved money.</p>
      {plan.checking_routes.length === 0 && plan.credit_routes.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No balance-based route is available with the current account balances and reserve.</p> : <div className="mt-4 space-y-2">
        {plan.checking_routes.map((route, index) => <div key={`checking-${index}`} className="flex flex-col gap-1 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="text-emerald-950">{cashNames[route.from_last4] || `••${route.from_last4}`} → {cashNames[route.to_last4] || `••${route.to_last4}`} <span className="text-emerald-800">· checking coverage</span></span><strong className="tabular-nums text-emerald-950">Up to {money(route.amount_cents)}</strong></div>)}
        {plan.credit_routes.map((route, index) => <div key={`credit-${index}`} className="flex flex-col gap-1 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="text-blue-950">{cashNames[route.from_last4] || `••${route.from_last4}`} → {creditNames[route.to_last4] || `••${route.to_last4}`} <span className="text-blue-800">· payoff unverified</span></span><strong className="tabular-nums text-blue-950">Up to {money(route.amount_cents)}</strong></div>)}
      </div>}
    </div>
  </section>
}
