import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { financeApi, financeError, type PaymentAccount, type PaymentBalanceLink, type PaymentBalanceSource } from '../services/finance'
import { accountControl as control, accountPrimary as primary } from './paymentAccountStyles'

export default function PaymentAccountBalance({account}: {account: PaymentAccount}) {
  const [sources, setSources] = useState<PaymentBalanceSource[]>([])
  const [links, setLinks] = useState<PaymentBalanceLink[]>([])
  const [monitorAvailable, setMonitorAvailable] = useState(false)
  const [choice, setChoice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  useEffect(() => {
    let active = true
    Promise.all([financeApi.paymentSources(), financeApi.paymentBalances(account.id)]).then(([data, connected]) => {
      if (!active) return
      setSources(data.items.filter(s => s.account_type === account.account_type && (s.provider !== 'ledger' || account.ownership === 'business')))
      setMonitorAvailable(data.monitor_available); setLinks(connected)
    }).catch(e => { if (active) setError(financeError(e)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [account.id, account.account_type, account.ownership])
  async function connect() {
    const source = sources.find(s => `${s.provider}|${s.id}` === choice)
    if (!source) return
    setBusy(true); setError(''); setNotice('')
    try {
      await financeApi.linkPaymentAccount(account.id, {provider: source.provider, source_id: source.id, previous_id: links.find(l => l.provider === source.provider)?.link_id || null})
      setLinks(await financeApi.paymentBalances(account.id)); setNotice('Balance source connected.'); setChoice('')
    } catch(e) { setError(financeError(e)) } finally { setBusy(false) }
  }
  return <div className="mt-4 space-y-4 border-t border-slate-200 pt-4 text-sm">
    {loading && <p role="status">Loading balance sources…</p>}
    {links.map(l => <div key={l.link_id} className="flex flex-wrap justify-between gap-3"><div><p className="font-medium">{l.provider === 'monitor' ? (account.account_type === 'card' ? 'Card amount owed (monitored)' : 'Monitored balance') : 'Statement balance'}</p><p className="mt-1 text-slate-600">{l.source ? `${l.source.name} · ${l.source.as_of ? `As of ${l.source.as_of}` : 'No balance recorded'}` : l.reason}</p></div><div className="text-right"><p className="text-lg font-semibold tabular-nums">{l.source?.balance == null ? 'Not available' : Number(l.source.balance).toLocaleString('en-US', {style:'currency', currency:'USD'})}</p><p className="text-slate-600">{l.provider === 'monitor' ? 'Observed · not reconciled' : l.source?.basis === 'reconciled_statement' ? 'Reconciled statement' : 'Awaiting statement'}</p></div></div>)}
    {!loading && !links.length && <p className="text-slate-600">No balance source connected yet.</p>}
    {sources.length > 0 && <div className="max-w-2xl space-y-3"><label className="block font-medium">Connect to an existing account<select className={control} value={choice} onChange={e => setChoice(e.target.value)}><option value="">Select the matching account</option>{sources.map(s => <option key={`${s.provider}|${s.id}`} value={`${s.provider}|${s.id}`}>{s.name}{s.last4 ? ` · ••${s.last4}` : ''} · {s.provider === 'monitor' ? 'Bank Monitor' : 'Accounting statements'}</option>)}</select></label><button type="button" disabled={!choice || busy} onClick={connect} className={primary}>{busy ? 'Connecting…' : 'Connect balance source'}</button></div>}
    {!loading && !sources.length && <p className="text-slate-600">No matching balance sources are available. {account.ownership === 'business' ? <Link className="font-medium text-blue-700 underline underline-offset-4" to="/finance/money">Add an account and statement in Money & Accounting.</Link> : 'Personal balances stay outside the business cash ledger.'}</p>}
    {!monitorAvailable && <p className="text-slate-600">Monitored sources require a signed-in Bank Monitor session with access to this business.</p>}
    <p className="max-w-prose text-slate-600">A monitored balance is a dated observation. Only reconciled business statements support available cash; personal balances do not enter business cash.</p>
    {notice && <p role="status" className="text-emerald-800">{notice}</p>}{error && <p role="alert" className="text-red-700">{error}</p>}
  </div>
}
