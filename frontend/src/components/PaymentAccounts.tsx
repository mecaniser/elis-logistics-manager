import { useEffect, useRef, useState, useId } from 'react'
import { financeApi, financeError, type PaymentAccount } from '../services/finance'
import { useTenant } from '../contexts/TenantContext'
import { accountControl as control, accountPrimary as primary, accountSecondary as secondary } from './paymentAccountStyles'
import PaymentAccountBalance from './PaymentAccountBalance'

const types = [{value: 'card', label: 'Credit card'}, {value: 'bank', label: 'Bank account'}, {value: 'cash', label: 'Cash'}] as const
function AccountIcon({type}: {type: PaymentAccount['account_type']}) {
  return <svg aria-hidden="true" className="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{type === 'card' ? <><rect x="2" y="4" width="20" height="16" rx="3"/><path d="M2 9h20M6 15h4"/></> : type === 'bank' ? <><path d="m3 8 9-5 9 5H3ZM3 21h18M5 11v7M10 11v7M14 11v7M19 11v7"/></> : <><rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M5 12h1M18 12h1"/></>}</svg>
}
export function PaymentAccountEditor({ onAdded, onCancel, initialType = 'card' }: { onAdded: (account: PaymentAccount) => void; onCancel?: () => void; initialType?: PaymentAccount['account_type'] }) {
  const typeGroup = useId()
  const [name, setName] = useState('')
  const [last4, setLast4] = useState('')
  const [type, setType] = useState(initialType)
  const [ownership, setOwnership] = useState<PaymentAccount['ownership']>(initialType === 'card' ? 'personal' : 'business')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const nameRef = useRef<HTMLInputElement>(null)
  useEffect(() => { nameRef.current?.focus() }, [])
  async function save() {
    if (!name.trim() || (last4 && !/^\d{4}$/.test(last4))) { setError('Enter a nickname and, optionally, exactly four last digits.'); return }
    setBusy(true); setError('')
    try { onAdded(await financeApi.addPaymentAccount({name: name.trim(), last4: type === 'cash' ? '' : last4, account_type: type, ownership})) }
    catch (e) { setError(financeError(e)) } finally { setBusy(false) }
  }
  return <div className="max-w-2xl space-y-5 border-t border-slate-200 pt-5 text-sm" onKeyDown={e => { if (e.key === 'Enter' && e.target instanceof HTMLInputElement) { e.preventDefault(); if (!busy) void save() } }}>
    <h3 className="text-lg font-semibold text-slate-950">Add payment account</h3>
    <fieldset disabled={busy} className="space-y-5">
      <legend className="mb-2 font-medium">What do you use to pay?</legend>
      <div className="grid grid-cols-3 gap-2">{types.map(t => <label key={t.value} className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border px-2 py-3 text-center has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-blue-600 ${type === t.value ? 'border-blue-600 bg-blue-50 text-blue-900' : 'border-slate-300 text-slate-700 hover:bg-slate-50'}`}><input type="radio" name={typeGroup} className="sr-only" checked={type === t.value} onChange={() => { setType(t.value); setLast4('') }} /><AccountIcon type={t.value}/><span className="font-medium">{t.label}</span></label>)}</div>
      <label className="block font-medium">Account nickname<input ref={nameRef} className={control} maxLength={80} placeholder={type === 'card' ? 'e.g. Chase Sapphire' : type === 'bank' ? 'e.g. Business checking' : 'e.g. Business cash'} value={name} onChange={e => setName(e.target.value)} /></label>
      <div className="grid gap-4 sm:grid-cols-2"><label className="font-medium">Whose account is this?<select className={control} value={ownership} onChange={e => setOwnership(e.target.value as PaymentAccount['ownership'])}><option value="personal">Personal</option><option value="business">Business</option></select></label>
      {type !== 'cash' && <label className="font-medium">Last four digits <span className="font-normal text-slate-600">(optional)</span><input className={control} inputMode="numeric" maxLength={4} placeholder="1234" value={last4} onChange={e => setLast4(e.target.value)} /></label>}</div>
    </fieldset>
    <p className="max-w-prose leading-6 text-slate-600">{ownership === 'personal' ? 'Business purchases you pay personally can be tracked for reimbursement.' : 'Use this account to identify payments made with business money.'} Save the account, then connect an available balance source. No full card number or bank login is needed here.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">{onCancel && <button type="button" disabled={busy} onClick={onCancel} className={secondary}>Cancel</button>}<button type="button" disabled={busy} onClick={save} className={primary}>{busy ? 'Saving…' : 'Save account'}</button></div>
  </div>
}

export default function PaymentAccounts() {
  const { currentTenant } = useTenant()
  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [loadedTenant, setLoadedTenant] = useState<number>()
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  const [connected, setConnected] = useState<string | null>(null)
  const addRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    let active = true
    setAccounts([]); setLoadedTenant(undefined); setError(''); setAdding(false); setConnected(null)
    if (currentTenant?.id) financeApi.paymentAccounts().then(items => { if (active) { setAccounts(items); setLoadedTenant(currentTenant.id) } }).catch(e => { if (active) setError(financeError(e)) })
    return () => { active = false }
  }, [currentTenant?.id])
  function closeEditor() { setAdding(false); requestAnimationFrame(() => addRef.current?.focus()) }
  return <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="max-w-2xl"><h2 className="text-xl font-semibold text-slate-950">Payment accounts</h2><p className="mt-1 text-sm leading-6 text-slate-600">Choose the card, bank account or cash source used for each repair. Keep personal funding separate from business cash.</p></div>
      {!adding && <button ref={addRef} type="button" disabled={loadedTenant !== currentTenant?.id} onClick={() => setAdding(true)} className={primary}><svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>Add account</button>}
    </div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {loadedTenant === currentTenant?.id && currentTenant && <>
      {!adding && !accounts.length && <div className="flex items-center gap-4 border-t border-slate-200 py-5 text-slate-600"><AccountIcon type="card"/><div><p className="font-medium text-slate-900">Add your first payment account</p><p className="mt-1 text-sm">Save it once, then select it on any repair payment.</p></div></div>}
      {accounts.length > 0 && <ul className="divide-y divide-slate-200">{accounts.map(a => <li key={a.id} className="py-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><AccountIcon type={a.account_type}/><div><p className="font-semibold text-slate-950">{a.name}{a.last4 && <span className="ml-2 font-normal text-slate-600">••{a.last4}</span>}</p><p className="text-sm text-slate-600">{a.ownership === 'personal' ? 'Personal' : 'Business'} · {types.find(t => t.value === a.account_type)?.label}</p></div></div><button type="button" className={secondary} aria-expanded={connected === a.id} onClick={() => setConnected(connected === a.id ? null : a.id)}>{connected === a.id ? 'Hide balance details' : 'Balance & connection'}</button></div>{connected === a.id && <PaymentAccountBalance account={a}/>}</li>)}</ul>}
      {adding && <PaymentAccountEditor key={currentTenant.id} onCancel={closeEditor} onAdded={a => { setAccounts(items => [...items.filter(i => i.id !== a.id), a]); closeEditor(); setConnected(a.id) }} />}
    </>}
    {!error && loadedTenant !== currentTenant?.id && <p role="status" className="text-sm text-slate-600">Loading payment accounts…</p>}
  </section>
}
