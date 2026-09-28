import { useEffect, useState } from 'react'
import { bankMonitorApi } from '../services/api'

type Usage = {
  tracking_enabled: boolean; environment: string; period_start: string; as_of: string; first_recorded_at: string | null; last_recorded_at: string | null
  calls: number; successful_balance_reads: number; balance_rate_usd: string | null; balance_estimate_usd: string | null
  transactions_free_exhausted_at: string | null
  endpoints: { endpoint: string; calls: number; successful: number; failed: number; unknown: number }[]
}
const dollars = (value: string) => Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const labels: Record<string, string> = { '/accounts/balance/get': 'Live balances', '/transactions/sync': 'Transaction history', '/transactions/get': 'Transaction history', '/transactions/refresh': 'Transaction refresh', '/liabilities/get': 'Liabilities', '/accounts/get': 'Account list', '/item/get': 'Connection checks', '/link/token/create': 'Bank sign-in', '/item/public_token/exchange': 'Bank connection', '/item/remove': 'Disconnect bank' }

export default function PlaidUsageSummary({ tenantId }: { tenantId: number }) {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState(false)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    setBusy(true); setError(false)
    bankMonitorApi.plaidUsage(tenantId).then(({ data }) => { if (active) setUsage(data) })
      .catch(() => { if (active) setError(true) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [tenantId, version])
  const tracked = Boolean(usage?.first_recorded_at)
  return <section aria-label="Plaid API usage" className="rounded-xl border border-slate-200 bg-white px-4 py-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)} className="flex min-h-9 items-center gap-2 text-sm font-semibold text-slate-900">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`h-4 w-4 transition-transform ${open ? 'rotate-90' : ''}`}><path d="m9 18 6-6-6-6" /></svg>Plaid usage
        <span className="font-normal text-slate-500">This month · UTC</span>
      </button>
      <button type="button" disabled={busy} onClick={() => setVersion(value => value + 1)} aria-label="Refresh Plaid usage summary" title="Refresh recorded usage, without calling Plaid" className="grid h-9 w-9 place-items-center rounded-lg text-blue-700 hover:bg-blue-50 disabled:opacity-40"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`h-4 w-4 ${busy ? 'animate-spin motion-reduce:animate-none' : ''}`}><path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1" /></svg></button>
    </div>
    {error ? <p role="alert" className="text-sm text-amber-800">Usage could not be loaded. Try refreshing this summary.</p> : !usage ? <p className="text-sm text-slate-500">Loading usage…</p> : <>
      {usage.transactions_free_exhausted_at && <p className="mb-2 text-sm font-medium text-amber-800">Transactions: free allowance exhausted. Further usage is billable.</p>}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-slate-500">Recorded API calls</dt><dd className="font-semibold tabular-nums">{tracked ? usage.calls.toLocaleString() : 'Not recorded yet'}</dd></div>
        <div><dt className="text-xs text-slate-500">Successful balance reads</dt><dd className="font-semibold tabular-nums">{tracked ? usage.successful_balance_reads.toLocaleString() : '—'}</dd></div>
        <div><dt className="text-xs text-slate-500">Balance cost estimate*</dt><dd className="font-semibold tabular-nums">{usage.balance_estimate_usd === null ? 'Not available' : dollars(usage.balance_estimate_usd)}</dd></div>
        <div><dt className="text-xs text-slate-500">Plaid billable usage / total</dt><dd className="font-semibold">Unconfirmed</dd></div>
      </dl>
      <p className="mt-2 text-xs text-slate-500">ELIS integration · All businesses · {usage.environment}. {tracked ? `Calls recorded since ${new Date(usage.first_recorded_at!).toLocaleString()}.` : usage.tracking_enabled ? 'Tracking begins with the next Plaid call.' : 'Call tracking is not enabled.'} Earlier calls are not included.</p>
      {open && <div className="mt-3 space-y-3 border-t border-slate-200 pt-3 text-sm">
        <p className="text-slate-600">*Balance reads only{usage.balance_rate_usd ? ` at ${dollars(usage.balance_rate_usd)} per successful call` : ''}, before free allowances or credits. Monthly subscriptions and other products are excluded. This is not your invoice.</p>
        {usage.transactions_free_exhausted_at && <p className="text-slate-600">Transactions allowance status confirmed by Plaid email on {new Date(usage.transactions_free_exhausted_at).toLocaleDateString()}. This is a saved notice, not a live allowance balance.</p>}
        {!!usage.endpoints.length && <div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="sr-only">Recorded Plaid requests this month</caption><thead><tr className="text-slate-500"><th className="py-2">Activity</th><th>Calls</th><th>Successful</th><th>Failed</th><th>Unknown</th></tr></thead><tbody>{usage.endpoints.map(row => <tr key={row.endpoint} className="border-t border-slate-100"><th scope="row" title={row.endpoint} className="py-2 pr-3 font-medium">{labels[row.endpoint] || row.endpoint}</th><td>{row.calls}</td><td>{row.successful}</td><td>{row.failed}</td><td>{row.unknown}</td></tr>)}</tbody></table></div>}
        <p className="text-xs text-slate-500">Unknown means no confirmed response, such as a timeout. Usage refresh reads ELIS records only; it does not refresh bank data. Updated {new Date(usage.as_of).toLocaleString()}.</p>
        <div className="flex flex-wrap gap-4"><a href="https://dashboard.plaid.com/activity/usage" target="_blank" rel="noreferrer" className="font-medium text-blue-700">Plaid usage ↗</a><a href="https://dashboard.plaid.com/settings/team/billing" target="_blank" rel="noreferrer" className="font-medium text-blue-700">Rates & invoices ↗</a></div>
      </div>}
    </>}
  </section>
}
