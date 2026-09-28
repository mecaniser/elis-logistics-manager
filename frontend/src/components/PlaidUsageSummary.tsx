import { useEffect, useState } from 'react'
import { bankMonitorApi } from '../services/api'

type Product = { name: string; used: number | null; limit: number | null; exhausted?: boolean; rate: string }
type Usage = {
  environment: string; first_recorded_at: string | null; calls: number
  allowance_snapshot: { checked_at: string; products: Product[] } | null
  endpoints: { endpoint: string; calls: number; successful: number; failed: number; unknown: number }[]
}
type Dashboard = { status: string; checked_at?: string; metrics: { metric: string; observations: number; series: unknown[] }[] }
const labels: Record<string, string> = { '/accounts/balance/get': 'Live balances', '/transactions/sync': 'Transaction history', '/transactions/get': 'Transaction history', '/transactions/refresh': 'Transaction refresh', '/liabilities/get': 'Liabilities', '/accounts/get': 'Account list', '/item/get': 'Connection checks', '/link/token/create': 'Bank sign-in', '/item/public_token/exchange': 'Bank connection', '/item/remove': 'Disconnect bank' }
const date = (value: string) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

export default function PlaidUsageSummary({ tenantId }: { tenantId: number }) {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState(false)
  const [error, setError] = useState(false)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!open) return
    let active = true
    setBusy(true); setError(false)
    Promise.allSettled([bankMonitorApi.plaidUsage(tenantId), bankMonitorApi.plaidDashboardUsage(tenantId)]).then(([local, provider]) => {
      if (!active) return
      if (local.status === 'fulfilled') setUsage(local.value.data)
      else setError(true)
      setDashboard(provider.status === 'fulfilled' ? provider.value.data : { status: 'unavailable', metrics: [] })
      setBusy(false)
    })
    return () => { active = false }
  }, [tenantId, version, open])
  const snapshot = usage?.allowance_snapshot
  const month = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })
  return <section aria-label="Plaid API usage" className="rounded-xl border border-slate-200 bg-white px-4 py-2">
    <button type="button" aria-expanded={open} aria-controls="plaid-usage-content" onClick={() => setOpen(value => !value)} className="flex min-h-11 w-full items-center gap-2 rounded-lg text-left text-sm font-semibold text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600">
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`h-4 w-4 shrink-0 ${open ? 'rotate-90' : ''}`}><path d="m9 18 6-6-6-6" /></svg>
      Plaid usage & costs<span className="ml-auto text-xs font-normal text-slate-600">{open ? 'Hide' : 'View'}</span>
    </button>
    {open && <div id="plaid-usage-content" className="space-y-4 border-t border-slate-200 py-4">
      {error && <p role="alert" className="text-sm text-amber-800">Couldn’t load usage. Try again.</p>}
      {!usage && busy && <p role="status" className="text-sm text-slate-600">Loading usage…</p>}
      {usage && <>
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-sm font-semibold text-slate-900">Free allowance</h3><span className="text-xs text-slate-600">{snapshot ? `Saved from Plaid · ${date(snapshot.checked_at)}` : 'No allowance snapshot'}</span></div>
        {snapshot && <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-left text-sm tabular-nums"><caption className="sr-only">Saved free request allowance and contracted rates; not live counters</caption>
          <thead className="text-xs text-slate-600"><tr><th scope="col" className="pb-2 pr-4">Product</th><th scope="col" className="pb-2 pr-4">Free requests used</th><th scope="col" className="pb-2 pr-4 text-right">Free left</th><th scope="col" className="pb-2 pl-4">Rate after free usage</th></tr></thead>
          <tbody>{snapshot.products.map(product => <tr key={product.name} className="border-t border-slate-100">
            <th scope="row" className="py-3 pr-4 font-medium text-slate-900">{product.name}</th>
            <td className="w-1/3 py-3 pr-4"><div className="mb-1 flex justify-between gap-2 text-xs"><span>{product.exhausted ? 'Exhausted' : `${product.used} / ${product.limit}`}</span><span className={product.exhausted ? 'font-medium text-amber-800' : 'text-slate-600'}>{product.exhausted ? 'Paid usage' : 'Free tier'}</span></div><div role="meter" aria-label={`${product.name} free allowance used`} aria-valuemin={0} aria-valuemax={product.limit ?? 100} aria-valuenow={product.exhausted ? (product.limit ?? 100) : product.used ?? 0} aria-valuetext={product.exhausted ? 'Free allowance exhausted' : `${product.used} of ${product.limit} free requests used`} className="h-2 overflow-hidden rounded bg-slate-200"><div className={`h-full ${product.exhausted ? 'bg-amber-600' : 'bg-blue-600'}`} style={{ width: `${product.exhausted ? 100 : product.limit ? Math.min(100, (product.used ?? 0) / product.limit * 100) : 0}%` }} /></div></td>
            <td className="pr-4 text-right font-semibold">{product.exhausted ? 0 : product.limit !== null && product.used !== null ? Math.max(0, product.limit - product.used) : '—'}</td><td className="pl-4 text-xs text-slate-700">{product.rate}</td>
          </tr>)}</tbody></table></div>}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-4"><h3 className="text-sm font-semibold text-slate-900">Activity · {month}</h3><button type="button" disabled={busy} onClick={() => setVersion(value => value + 1)} className="min-h-9 rounded px-2 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50">{busy ? 'Checking…' : 'Refresh activity'}</button></div>
        <dl className="grid grid-cols-2 gap-4 text-sm"><div><dt className="text-slate-600">ELIS requests recorded</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{usage.calls.toLocaleString()}</dd></div><div><dt className="text-slate-600">Plaid billable usage</dt><dd className="mt-1 font-semibold text-slate-900">{dashboard?.status === 'unavailable' ? 'Couldn’t retrieve' : dashboard?.metrics.some(row => row.observations > 0) ? 'See Plaid report' : 'Awaiting Plaid data'}</dd></div></dl>
        <p className="text-xs text-slate-600">{usage.first_recorded_at ? `ELIS tracking since ${date(usage.first_recorded_at)}.` : 'ELIS tracking starts with the next bank request.'} Allowance bars are a saved snapshot, not live counters.</p>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs font-medium text-blue-700"><button type="button" aria-expanded={detail} onClick={() => setDetail(value => !value)} className="min-h-9 hover:underline">{detail ? 'Hide request details' : 'Request details'}</button><a href="https://dashboard.plaid.com/settings/team/products" target="_blank" rel="noreferrer" className="py-2 hover:underline">Live allowances</a><a href="https://dashboard.plaid.com/settings/team/billing" target="_blank" rel="noreferrer" className="py-2 hover:underline">Rates & invoices</a></div>
        {detail && <div className="space-y-3 text-xs"><p className="text-slate-600">All businesses · {usage.environment} · UTC month. Bank requests and monthly subscription charges are different units.</p>{usage.endpoints.length ? <div className="overflow-x-auto"><table className="w-full text-left tabular-nums"><thead className="text-slate-600"><tr><th className="pb-2">Activity</th><th>Calls</th><th>Success</th><th>Failed</th><th>Unknown</th></tr></thead><tbody>{usage.endpoints.map(row => <tr key={row.endpoint} className="border-t border-slate-100"><th scope="row" title={row.endpoint} className="py-2 pr-3 font-medium">{labels[row.endpoint] || row.endpoint}</th><td>{row.calls}</td><td>{row.successful}</td><td>{row.failed}</td><td>{row.unknown}</td></tr>)}</tbody></table></div> : <p>No requests recorded yet.</p>}<p className="text-slate-600">{dashboard?.checked_at ? `Plaid checked ${new Date(dashboard.checked_at).toLocaleString()}. Reports refresh at most hourly.` : 'Plaid report has not loaded.'} Refreshing this report does not refresh bank accounts.</p><a href="https://dashboard.plaid.com/activity/usage" target="_blank" rel="noreferrer" className="inline-block py-2 font-medium text-blue-700">Open Plaid usage report</a></div>}
      </>}
    </div>}
  </section>
}
