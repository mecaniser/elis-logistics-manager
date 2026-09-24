import { useState, useId, useEffect, type FormEvent } from 'react'
import { financeApi, financeError, type PaymentAccount } from '../../services/finance'
import { PaymentAccountEditor } from '../PaymentAccounts'
import { repairMoney, type RepairReviewRow } from './repairReview'

export default function RepairPaymentReview({ rows, onSaved }: { rows: RepairReviewRow[]; onSaved: () => void }) {
  const payeeListId = useId()
  const prior = rows.length === 1 ? rows[0].confirmation : null
  const [payee, setPayee] = useState(prior?.payee || (rows.length === 1 ? rows[0].payee?.name || '' : ''))
  const [status, setStatus] = useState(prior?.status || 'paid')
  const [method, setMethod] = useState(prior?.method || 'unknown')
  const [source, setSource] = useState(prior?.source || 'unknown')
  const [amount, setAmount] = useState(prior?.paid_amount || '')
  const [paidDate, setPaidDate] = useState(prior ? prior.paid_date || '' : rows.length === 1 ? rows[0].date || '' : '')
  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [accountId, setAccountId] = useState(prior?.payment_account_id || '')
  const [accountError, setAccountError] = useState('')
  const [addingAccount, setAddingAccount] = useState(false)
  useEffect(() => {
    let active = true
    financeApi.paymentAccounts().then(items => { if (active) setAccounts(items) }).catch(e => { if (active) setAccountError(financeError(e)) })
    return () => { active = false }
  }, [])
  const accountType = method === 'credit_card' ? 'card' : method === 'zelle' ? 'bank' : method === 'cash' ? 'cash' : null
  const matchingAccounts = accounts.filter(a => a.account_type === accountType)
  function selectAccount(id: string) {
    setAccountId(id)
    const account = accounts.find(a => a.id === id)
    if (account) setSource(account.ownership)
  }
  const [note, setNote] = useState(prior?.note || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const paid = status === 'paid' || status === 'partial'
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setSaved(false)
    try {
      await financeApi.confirmRepairs({items: rows.map(r => ({repair_id: r.legacy_id, snapshot: r.review_snapshot, previous_id: r.confirmation?.id || null})), status,
        method: paid ? method : 'unknown', source: paid ? source : 'unknown', paid_amount: status === 'partial' ? amount : null,
        payment_account_id: paid && accountId ? accountId : null, paid_date: paid && paidDate ? paidDate : null, note, payee: payee.trim() || null})
      setSaved(true); onSaved()
    } catch (e) { setError(financeError(e)) }
    finally { setBusy(false) }
  }
  const control = 'block w-full min-h-11 border border-gray-300 rounded-md px-3 text-base mt-1 focus-visible:outline-blue-600 bg-white'
  return <form onSubmit={save} className="space-y-3 py-3 text-sm text-gray-700">
    <p>{rows.length === 1 ? `Saved repair amount: ${repairMoney(rows[0].recorded_cost)}` : `These answers apply to all ${rows.length} selected repairs. Unselect any exceptions first.`}</p>
    <label className="block">Paid to / vendor{rows.length > 1 ? ' (leave blank to keep individual vendors)' : ''}<input className={control} list={payeeListId} maxLength={160} value={payee} onChange={e => setPayee(e.target.value)} placeholder="Vendor or person’s name" /></label>
    <datalist id={payeeListId}><option value="CaroMeck Diesel PM LLC" /><option value="Truck Pit Stop" /><option value="Tarpstop" /></datalist>
    <label className="block">Was this paid?<select className={control} required value={status} onChange={e => setStatus(e.target.value)}>
      <option value="">Choose…</option><option value="paid">Yes, paid in full</option>{rows.length === 1 && <option value="partial">Partly paid</option>}<option value="unpaid">Not paid yet</option><option value="unknown">I’m not sure</option>
    </select></label>
    {paid && <>
      <label className="block">How was it paid?<select className={control} value={method} onChange={e => { setMethod(e.target.value); setAccountId('') }}><option value="unknown">Not sure</option><option value="cash">Cash</option><option value="zelle">Zelle</option><option value="credit_card">Credit card</option><option value="other">Other / multiple methods</option></select></label>
      <label className="block">Whose money?<select className={control} value={source} onChange={e => { setSource(e.target.value); setAccountId('') }}><option value="unknown">Not sure</option><option value="business">Business money</option><option value="personal">My personal money</option><option value="mixed">A mix</option></select></label>
      {accountType && <div className="space-y-2">
        <label className="block">Which {accountType === 'card' ? 'credit card' : accountType === 'bank' ? 'bank account' : 'cash source'}?<select className={control} value={accountId} onChange={e => selectAccount(e.target.value)}><option value="">Not identified yet</option>{matchingAccounts.map(a => <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` · ••${a.last4}` : ''} · {a.ownership === 'personal' ? 'Personal' : 'Business'}</option>)}</select></label>
        {accountError && <p role="alert" className="text-red-700">{accountError}</p>}
        <button type="button" aria-expanded={addingAccount} className="min-h-11 text-blue-700 underline" onClick={() => setAddingAccount(!addingAccount)}>{addingAccount ? 'Cancel adding account' : 'Add a payment account'}</button>
        {addingAccount && <PaymentAccountEditor onAdded={a => { setAccounts(items => [...items.filter(i => i.id !== a.id), a]); if (a.account_type === accountType) { setSource(a.ownership); setAccountId(a.id) } setAddingAccount(false) }} />}
      </div>}
      {status === 'partial' && <label className="block">Total paid so far<input className={control} type="number" min="0.01" step="0.01" required value={amount} onChange={e => setAmount(e.target.value)} /></label>}
      {rows.length === 1 && !prior && rows[0].date && <p>Payment date defaults to the invoice date. Change it if payment happened on another day.</p>}
      {rows.length === 1 && <label className="block">Payment date<input className={control} type="date" value={paidDate} onChange={e => setPaidDate(e.target.value)} /></label>}
    </>}
    {paid && source === 'personal' && <p className="font-medium text-blue-800">Paid with your personal money: this belongs in amounts the business owes you, less anything already reimbursed. Saving here preserves the details; the Accounting reimbursement entry is not created yet.</p>}
    <label className="block">Note or payment reference (optional)<input className={control} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
    <p>Your answers are saved as your confirmation. Unknown dates and funding sources can stay unknown. This does not add another expense or change bank balances.</p>
    <button disabled={busy || !rows.length} className="min-h-11 px-4 py-2 bg-blue-700 text-white rounded-md hover:bg-blue-800 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">{busy ? 'Saving…' : 'Save payment details'}</button>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {saved && <p role="status">Payment details saved as your confirmation.</p>}
  </form>
}

export function RepairBatchReview({rows, onSaved}: {rows: RepairReviewRow[]; onSaved: () => void}) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const eligible = rows.filter(r => r.batch_eligible)
  const chosen = eligible.filter(r => selected.includes(r.legacy_id))
  return <div className="mt-3">
    <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="min-h-11 text-blue-700 underline focus-visible:outline focus-visible:outline-2">Confirm matching invoices together ({eligible.length})</button>
    {open && <div className="max-w-2xl space-y-3">
      <p className="text-sm text-gray-700">These extracted invoice totals match their saved repair amounts. Select only the repairs for which the same payment answers apply.</p>
      {!eligible.length && <p>No matching invoices need a first confirmation.</p>}
      {eligible.length > 0 && <button type="button" className="min-h-11 text-blue-700 underline focus-visible:outline focus-visible:outline-2" onClick={() => setSelected(chosen.length === eligible.length ? [] : eligible.map(r => r.legacy_id))}>{chosen.length === eligible.length ? 'Clear selection' : 'Select all matching invoices'}</button>}
      <div className="max-h-80 overflow-y-auto" role="group" aria-label="Matching invoices">{eligible.map(r => <label key={r.legacy_id} className="flex gap-3 items-start min-h-11 py-2 text-sm"><input type="checkbox" className="mt-1" checked={selected.includes(r.legacy_id)} onChange={e => setSelected(e.target.checked ? [...selected, r.legacy_id] : selected.filter(id => id !== r.legacy_id))} /><span>{r.payee?.name || 'Payee not identified'} · {r.date} · {r.asset_name}<br />{r.description} · <strong>{repairMoney(r.recorded_cost)}</strong></span></label>)}</div>
      {chosen.length > 0 && <RepairPaymentReview key={chosen.map(r => r.legacy_id).join(',')} rows={chosen} onSaved={() => {setSelected([]); onSaved()}} />}
    </div>}
  </div>
}
