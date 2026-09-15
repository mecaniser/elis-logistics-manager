import { useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'
import BankTransferQueue from './BankTransferQueue'
import { useTenant } from '../contexts/TenantContext'

type Account = { nickname: string; last4: string }
type Repayment = { enabled: boolean; priority: string[]; reserve_cents: number | null }
type Rules = { repayment: Repayment; enabled: boolean; checking: Account[]; sources: Account[]; basis: string; buffer_cents: number }
type Run = { id: number; scheduled_date: string; started_at: string; status: string; result: {
  credit_accounts?: { last4: string; nickname: string; outstanding_cents: number | null; accrued_interest_cents: number | null }[];
  repayment?: { status: string; proposals: { from_last4: string; to_last4: string; amount_cents: number }[] };
  observed_at?: string; uncovered_cents?: number; message?: string;
  accounts?: { last4: string; nickname: string; current_cents: number; available_cents: number | null; needed_cents: number }[];
  proposals?: { from_last4: string; to_last4: string; amount_cents: number }[];
} }
type Dashboard = { rules: Rules; next_check: string; runs: Run[] }
const dollars = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const label = (status: string) => status.replace(/_/g, ' ')
const defaults: Rules = { repayment: { enabled: false, priority: [], reserve_cents: 0 }, enabled: false, checking: [], sources: [], basis: 'posted', buffer_cents: 0 }

export default function BankMonitor() {
  const { currentTenant } = useTenant()
  const tenantRef = useRef(currentTenant?.id)
  tenantRef.current = currentTenant?.id
  const [loadedTenant, setLoadedTenant] = useState<number | null>(null)
  const [data, setData] = useState<Dashboard | null>(null)
  const [rules, setRules] = useState<Rules>(defaults)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    if (!currentTenant) return
    const tenantId = currentTenant.id
    let active = true
    setData(null); setError(''); setNotice(''); setLoading(true)
    bankMonitorApi.get(tenantId).then(({ data: value }) => {
      if (active) { setData(value); setRules({ ...value.rules, repayment: value.rules.repayment || defaults.repayment }); setLoadedTenant(tenantId) }
    }).catch((e) => {
      if (active) setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Unable to load bank monitoring.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [currentTenant?.id])
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentTenant || loadedTenant !== currentTenant.id) return
    const tenantId = currentTenant.id
    setSaving(true); setError(''); setNotice('')
    try {
      await bankMonitorApi.save(tenantId, rules)
      if (tenantRef.current !== tenantId) return
      const response = await bankMonitorApi.get(tenantId)
      if (tenantRef.current !== tenantId) return
      setData(response.data)
      setNotice('Settings saved. Transfers remain off. The worker must be connected and running for scheduled checks.')
    } catch (e: any) {
      if (tenantRef.current !== tenantId) return
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Check account suffixes and ensure each account appears only once.')
    } finally { setSaving(false) }
  }
  const editAccount = (group: 'checking' | 'sources', index: number, key: keyof Account, value: string) => {
    setRules({ ...rules, [group]: rules[group].map((a, i) => i === index ? { ...a, [key]: value } : a) })
  }
  const importAccounts = (accounts: Account[]) => {
    const checking = accounts.filter(a => /checking/i.test(a.nickname))
    const sources = accounts.filter(a => /(line of credit|heloc|home equity)/i.test(a.nickname))
    setRules(current => ({
      ...current,
      checking: checking.length ? checking : current.checking,
      sources: sources.length ? [
        ...sources.filter(a => /(heloc|home equity)/i.test(a.nickname)),
        ...sources.filter(a => !/(heloc|home equity)/i.test(a.nickname)),
      ] : current.sources,
    }))
  }
  const latest = data?.runs[0]
  const stale = latest?.result.observed_at && Date.now() - Date.parse(latest.result.observed_at) > 300000
  return <div className="max-w-5xl mx-auto space-y-6">
    <div><h1 className="text-2xl font-semibold text-gray-900">Bank Monitor</h1>
      <p className="text-gray-600 mt-1">Daily business checking review at 5:30 p.m. Eastern.</p></div>
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="font-medium text-amber-900">Transfer proposals only · No money moves automatically</p>
      <p className="text-sm text-amber-900 mt-1">Checks calculate the amount needed to cover a shortfall. Complete any transfer in Truliant yourself. Fee avoidance and same-day posting have not been verified.</p>
    </div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {notice && <p role="status" className="text-green-800">{notice}</p>}
    {loading && <p role="status">Loading bank monitoring…</p>}
    {data && loadedTenant === currentTenant?.id && <>
      <section className="bg-white border rounded-lg p-5 space-y-3">
        <h2 className="text-lg font-semibold">Latest check</h2>
        {!latest ? <p className="text-gray-600">No checks recorded. Configure accounts, then connect the bank worker.</p> : <>
          <p className="font-medium capitalize">{label(latest.status)} · {latest.scheduled_date}</p>
          {latest.status === 'running' && <p>The check has not completed. If this persists, inspect the worker; no outcome is confirmed.</p>}
          {stale && <p className="text-amber-800">Historical snapshot. Recheck balances in Truliant before making a transfer.</p>}
          {latest.result.message && <p>{latest.result.message}</p>}
          <div className="overflow-x-auto">{latest.result.accounts && <table className="w-full text-sm text-left">
            <thead><tr><th className="py-2">Checking</th><th>Current</th><th>Available</th><th>Needed</th></tr></thead>
            <tbody>{latest.result.accounts.map(a => <tr key={a.last4} className="border-t"><td className="py-3">{a.nickname} · ••{a.last4}</td><td>{dollars(a.current_cents)}</td><td>{a.available_cents === null ? 'Unknown' : dollars(a.available_cents)}</td><td>{dollars(a.needed_cents)}</td></tr>)}</tbody>
          </table>}</div>
          {!!latest.result.proposals?.length && <p className="text-sm text-gray-600">This historical run contains aggregate balance estimates. Prepare individual full-charge transfers in the queue below; these estimates are not executable drafts.</p>}
          {latest.result.credit_accounts?.some(a => a.outstanding_cents !== null) && <div className="border-t pt-3">
            <h3 className="font-medium">Credit balances at last check</h3>
            {latest.result.credit_accounts.map(a => <p key={a.last4}>{a.nickname} · ••{a.last4}: balance {a.outstanding_cents === null ? 'unknown' : dollars(a.outstanding_cents)}, accrued interest {a.accrued_interest_cents === null ? 'unknown' : dollars(a.accrued_interest_cents)}</p>)}
            <p className="text-sm text-gray-600">These are reported balances, not verified payoff quotes.</p>
          </div>}
          {latest.result.repayment && <div className="border-t pt-3">
            <h3 className="font-medium">Friday credit repayment</h3>
            <p className="capitalize">{label(latest.result.repayment.status)}</p>
            {latest.result.repayment.status === 'repayment_data_required' && <p>Verified cleared income, pending debits, cash available without borrowing, and full credit balances are required before proposing repayment.</p>}
            {latest.result.repayment.proposals.map((p, i) => <p key={i}>Repayment proposed: {dollars(p.amount_cents)} from ••{p.from_last4} to ••{p.to_last4}</p>)}
          </div>}
          {!!latest.result.uncovered_cents && <p className="text-red-700">Uncovered shortfall: {dollars(latest.result.uncovered_cents)}. Listed credit cannot cover the full amount.</p>}
        </>}
        <a href="https://www.truliantfcuonline.org/dbank/live/app/home" target="_blank" rel="noreferrer" className="inline-block text-blue-700 underline">Open Truliant</a>
      </section>
      <BankTransferQueue key={currentTenant!.id} tenantId={currentTenant!.id} checking={rules.checking} sources={rules.sources} onAccountsDiscovered={importAccounts} />
      <form onSubmit={save} className="bg-white border rounded-lg p-5 space-y-5">
        <h2 className="text-lg font-semibold">Monitoring settings</h2>
        <p className="text-sm text-gray-600">Accounts are imported from Truliant when the bank assistant connects. Review the detected account types before saving.</p>
        {(['checking', 'sources'] as const).map(group => <fieldset key={group} className="space-y-3">
          <legend className="font-medium">{group === 'checking' ? 'Checking accounts' : 'Funding sources, in priority order'}</legend>
          {group === 'sources' && <p className="text-sm text-gray-600">Add your HELOC first and Preferred Line of Credit second. For a charge-level draft, use the first source that can cover the whole charge; do not split it.</p>}
          {rules[group].map((account, index) => <div key={index} className="flex flex-wrap items-end gap-3">
            <label className="text-sm flex-1">{group === 'sources' ? `Priority ${index + 1}` : `Account ${index + 1}`} nickname
              <input required maxLength={80} value={account.nickname} onChange={e => editAccount(group, index, 'nickname', e.target.value)} className="block border rounded p-2 w-full" /></label>
            <label className="text-sm">Last four digits<input required inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={account.last4} onChange={e => editAccount(group, index, 'last4', e.target.value)} className="block border rounded p-2 w-28" /></label>
            <button type="button" className="text-red-700 p-2" onClick={() => setRules({ ...rules, [group]: rules[group].filter((_, i) => i !== index) })} aria-label={`Remove ${group} ${index + 1}`}>Remove</button>
          </div>)}
          <button type="button" disabled={rules[group].length >= (group === 'checking' ? 10 : 5)} className="text-blue-700 underline disabled:opacity-50" onClick={() => setRules({ ...rules, [group]: [...rules[group], { nickname: '', last4: '' }] })}>Add {group === 'checking' ? 'checking account' : 'funding source'}</button>
        </fieldset>)}
        <label className="block text-sm">Shortfall coverage
          <select className="block border rounded p-2" value={rules.basis} onChange={e => setRules({ ...rules, basis: e.target.value })}>
            <option value="posted">Posted balance only</option>
            <option value="posted_and_pending">Posted balance plus verified pending debits</option>
          </select>
        </label>
        <p className="text-sm text-gray-600">Pending coverage stops when pending transactions cannot be verified. Available balance may include credit coverage and is never treated as cash for repayment. The separate server reader still needs live verification.</p>
        <fieldset className="border-t pt-4 space-y-3">
          <legend className="font-medium">Friday income repayment</legend>
          <p className="text-sm text-gray-600">At the Friday 5:30 p.m. check, preserve pending debits in both checking accounts and propose repayment from verified cleared business or salary income. No extra reserve. Pay the business credit line first, then the HELOC after the business line is fully paid.</p>
          <p className="text-sm text-amber-800">The bank reader can collect pending debits and credit balances, but cleared income, cash availability without borrowing, and payoff amounts still need verification. Missing information blocks repayment.</p>
          {[0, 1].map(index => <label key={index} className="block text-sm">{index === 0 ? 'Repay first: business credit line' : 'Repay second: HELOC'}
            <select className="block border rounded p-2" value={rules.repayment.priority[index] || ''} onChange={e => {
              const priority = [...rules.repayment.priority]; priority[index] = e.target.value
              setRules({ ...rules, repayment: { ...rules.repayment, priority } })
            }}>
              <option value="">Select credit source</option>
              {rules.sources.filter(a => /^[0-9]{4}$/.test(a.last4)).map(a => <option key={a.last4} value={a.last4}>{a.nickname} · ••{a.last4}</option>)}
            </select></label>)}
          <label className="flex gap-2 items-center"><input type="checkbox" checked={rules.repayment.enabled} onChange={e => setRules({ ...rules, repayment: { ...rules.repayment, enabled: e.target.checked, reserve_cents: 0 } })} />Include Friday repayment proposals when all required data is verified</label>
        </fieldset>
        <label className="flex gap-2 items-center"><input type="checkbox" checked={rules.enabled} onChange={e => setRules({ ...rules, enabled: e.target.checked })} />Request daily checks at 5:30 p.m. Eastern, including weekends</label>
        <p className="text-sm text-gray-600">{rules.enabled ? `Next scheduled time: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York' })} Eastern. This is a schedule, not confirmation that a worker is connected.` : 'Schedule is paused.'}</p>
        <button disabled={saving} className="bg-blue-700 text-white px-4 py-2 rounded disabled:opacity-50">{saving ? 'Saving…' : 'Save settings'}</button>
      </form>
      <section className="bg-white border rounded-lg p-5"><h2 className="text-lg font-semibold mb-3">Run history</h2>
        {data.runs.length ? data.runs.map(run => <p key={run.id} className="py-2 border-t">{run.scheduled_date} · <span className="capitalize">{label(run.status)}</span> · No transfers executed</p>) : <p className="text-gray-600">No scheduled runs yet.</p>}
      </section>
    </>}
  </div>
}
