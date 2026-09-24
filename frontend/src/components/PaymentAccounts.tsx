import { useEffect, useState } from 'react'
import { financeApi, financeError, type PaymentAccount } from '../services/finance'
import { useTenant } from '../contexts/TenantContext'

const control = 'mt-1 block min-h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-base'
export function PaymentAccountEditor({ onAdded }: { onAdded: (account: PaymentAccount) => void }) {
  const [name, setName] = useState('')
  const [last4, setLast4] = useState('')
  const [type, setType] = useState<PaymentAccount['account_type']>('card')
  const [ownership, setOwnership] = useState<PaymentAccount['ownership']>('personal')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save() {
    if (!name.trim() || (last4 && !/^\d{4}$/.test(last4))) { setError('Enter a nickname and, optionally, exactly four last digits.'); return }
    setBusy(true); setError('')
    try { const account = await financeApi.addPaymentAccount({name: name.trim(), last4: type === 'cash' ? '' : last4, account_type: type, ownership}); onAdded(account); setName(''); setLast4('') }
    catch (e) { setError(financeError(e)) } finally { setBusy(false) }
  }
  return <div onKeyDown={e => { if (e.key === 'Enter' && e.target instanceof HTMLInputElement) { e.preventDefault(); if (!busy) void save() } }} className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
    <label className="block">Account nickname<input className={control} maxLength={80} placeholder="e.g. Personal Chase card" value={name} onChange={e => setName(e.target.value)} /></label>
    <div className="grid gap-3 sm:grid-cols-2"><label>Account type<select className={control} value={type} onChange={e => { setType(e.target.value as PaymentAccount['account_type']); setLast4('') }}><option value="card">Credit card</option><option value="bank">Bank account</option><option value="cash">Cash</option></select></label>
    <label>Account ownership<select className={control} value={ownership} onChange={e => setOwnership(e.target.value as PaymentAccount['ownership'])}><option value="personal">My personal money</option><option value="business">Business money</option></select></label></div>
    {type !== 'cash' && <label className="block">Last four digits (optional)<input className={control} inputMode="numeric" maxLength={4} value={last4} onChange={e => setLast4(e.target.value)} /></label>}
    <p className="text-slate-600">Use a nickname and last four digits only. Adding an account does not connect its balance or enable transfers.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <button type="button" disabled={busy} onClick={save} className="min-h-11 rounded-md bg-blue-700 px-4 text-white hover:bg-blue-800 disabled:opacity-50">{busy ? 'Adding…' : 'Add payment account'}</button>
  </div>
}

export default function PaymentAccounts() {
  const { currentTenant } = useTenant()
  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [loadedTenant, setLoadedTenant] = useState<number>()
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  useEffect(() => {
    let active = true
    setAccounts([]); setLoadedTenant(undefined); setError(''); setAdding(false)
    if (currentTenant?.id) financeApi.paymentAccounts().then(items => { if (active) { setAccounts(items); setLoadedTenant(currentTenant.id) } }).catch(e => { if (active) setError(financeError(e)) })
    return () => { active = false }
  }, [currentTenant?.id])
  return <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
    <div><h2 className="text-xl font-semibold">Payment accounts</h2><p className="mt-1 text-sm text-slate-600">Save the personal cards, business bank accounts and cash sources you use for repairs. Choose one when confirming a payment.</p></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {loadedTenant === currentTenant?.id && <>
      {accounts.length ? <ul className="divide-y divide-slate-100">{accounts.map(a => <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-3"><span className="font-medium">{a.name}{a.last4 && ` · ••${a.last4}`}</span><span className="text-sm text-slate-600">{a.ownership === 'personal' ? 'Personal' : 'Business'} · {a.account_type === 'card' ? 'Credit card' : a.account_type === 'bank' ? 'Bank account' : 'Cash'}</span></li>)}</ul> : <p className="text-sm text-slate-600">No payment accounts saved for this business yet.</p>}
      <button type="button" aria-expanded={adding} onClick={() => setAdding(!adding)} className="min-h-11 text-blue-700 underline">{adding ? 'Cancel adding account' : 'Add a card, bank account or cash source'}</button>
      {adding && <PaymentAccountEditor key={currentTenant?.id} onAdded={a => { setAccounts(items => [...items.filter(i => i.id !== a.id), a]); setAdding(false) }} />}
    </>}
  </section>
}
