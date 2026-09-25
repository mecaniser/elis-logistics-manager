import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { financeApi, financeError } from '../services/finance'
import type { RepairReviewRow } from './repairs/repairReview'
import { accountControl as control, accountPrimary as primary, accountSecondary as secondary } from './paymentAccountStyles'

type Claim = {id: string; description: string; legacy_repair_id: number; remaining: string}
type Transaction = {id: string; date: string; description: string; account_id: string; account_name: string; unallocated: string}
type Reimbursements = {total_owed: string; claims: Claim[]; transactions: Transaction[]; as_of: string}
const usd = (value: string) => Number(value).toLocaleString('en-US', {style:'currency', currency:'USD'})
export default function OwnerReimbursements() {
  const [data, setData] = useState<Reimbursements | null>(null)
  const [rows, setRows] = useState<RepairReviewRow[]>([])
  const [settled, setSettled] = useState<RepairReviewRow[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [matching, setMatching] = useState('')
  const [transaction, setTransaction] = useState('')
  const [amount, setAmount] = useState('')
  const [selected, setSelected] = useState<number[]>([])
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let active = true
    Promise.all([financeApi.ownerReimbursements(), financeApi.repairHistory(new Date().toLocaleDateString('en-CA'))]).then(([money, history]) => { if (active) { setData(money as Reimbursements); setSettled(history.rows.filter(r => r.owner_posting?.status === 'historical_reimbursed')); setRows(history.rows.filter(r => r.owner_posting && ['ready','review_required'].includes(r.owner_posting.status))) } }).catch(e => { if(active) setError(financeError(e)) })
    return () => {active = false}
  }, [version])
  async function confirmSelected() {
    setBusy(true); setError('')
    try {
      await financeApi.confirmUnreimbursed(rows.filter(r => selected.includes(r.legacy_id)).map(r => ({repair_id: r.legacy_id, snapshot: r.review_snapshot, previous_id: r.confirmation?.id || null})))
      setSelected([]); setVersion(v => v + 1); setNotice('Selected payments confirmed as still owed. Eligible entries were recorded; any exceptions remain below.')
    } catch(e) {setError(financeError(e))} finally {setBusy(false)}
  }
  async function postReady() {
    setBusy(true); setError('')
    try { await financeApi.postOwnerRepairs(); setVersion(v => v + 1); setNotice('Eligible confirmations processed. Exceptions remain listed for review.') } catch(e) {setError(financeError(e))} finally {setBusy(false)}
  }
  async function match() {
    if (!data) return
    const t = data.transactions.find(t => t.id === transaction)
    if (!t) return
    setBusy(true); setError('')
    try {
      await financeApi.matchOwnerReimbursement(matching, {transaction_id: t.id, amount}, crypto.randomUUID())
      setMatching(''); setTransaction(''); setAmount(''); setVersion(v => v + 1); setNotice('Existing payment matched. The amount owed to you has been reduced.')
    } catch(e) {setError(financeError(e))} finally {setBusy(false)}
  }
  return <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">Owner reimbursements</h2><p className="mt-1 max-w-prose text-sm leading-6 text-slate-600">Business expenses paid with your personal money. Match repayments already made to you; this does not send money.</p></div>{data && <div className="text-right"><p className="text-sm text-slate-600">Recorded amount still owed</p><p className="text-2xl font-semibold tabular-nums">{usd(data.total_owed)}</p></div>}</div>
    {data && !data.claims.length && !settled.length && <p className="border-t border-slate-200 pt-4 text-sm text-slate-600">No repair reimbursement balances posted yet. Eligible personal-payment confirmations create them automatically.</p>}
    {settled.length > 0 && <div className="space-y-3 border-t border-slate-200 pt-4">
      <div><h3 className="font-semibold">Historical payments · reimbursed</h3><p className="mt-1 text-sm leading-6 text-slate-600">You confirmed these personal payments were repaid. They remain in your history with nothing outstanding. Repayment dates and bank transactions have not been verified.</p></div>
      {settled.map(row => <div key={row.legacy_id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="min-w-0 flex-1"><p className="font-medium text-slate-900">{row.description}</p><p className="mt-1 text-sm text-slate-600">Reimbursed—confirmed by owner</p></div>
        <div className="text-right text-sm tabular-nums"><p>Paid personally: <strong>{usd(row.confirmation?.paid_amount || '0')}</strong></p><p>Repaid: {usd(row.confirmation?.paid_amount || '0')}</p><p className="mt-1 font-semibold text-emerald-800">Still owed: $0.00</p></div>
      </div>)}
    </div>}
    {data?.claims.filter(c => Number(c.remaining) > 0).map(c => <div key={c.id} className="space-y-3 border-t border-slate-200 pt-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{c.description}</p><p className="text-sm text-slate-600">Still owed: <strong className="tabular-nums text-slate-900">{usd(c.remaining)}</strong></p></div><button type="button" className={secondary} aria-expanded={matching === c.id} onClick={() => {setMatching(matching === c.id ? '' : c.id); setTransaction(''); setAmount(c.remaining)}}>{matching === c.id ? 'Cancel matching' : 'Match reimbursement'}</button></div>
      {matching === c.id && <div className="max-w-2xl space-y-3"><label className="block text-sm font-medium">Payment already made to you<select className={control} value={transaction} onChange={e => setTransaction(e.target.value)}><option value="">Choose a reconciled business payment</option>{data.transactions.map(t => <option key={t.id} value={t.id}>{t.date} · {t.account_name} · {t.description} · {usd(t.unallocated)} available</option>)}</select></label><label className="block text-sm font-medium">Amount reimbursed<input type="number" min="0.01" step="0.01" max={c.remaining} className={control} value={amount} onChange={e => setAmount(e.target.value)}/></label>{!data.transactions.length && <p className="text-sm text-slate-600">Import the business bank statement or cashbook in <Link to="/finance/money" className="text-blue-700 underline underline-offset-4">Money & Accounting</Link> first.</p>}<button type="button" disabled={busy || !transaction || !amount} className={primary} onClick={match}>{busy ? 'Matching…' : 'Record matched reimbursement'}</button></div>}
    </div>)}
    {rows.length > 0 && <div className="space-y-3 border-t border-slate-200 pt-4"><h3 className="font-semibold">Confirmations awaiting accounting ({rows.length})</h3>{rows.map(r => <div key={r.legacy_id} className="text-sm"><label className="flex items-start gap-3 py-2 font-medium">{r.confirmation?.source === 'personal' && !r.confirmation.stale && r.confirmation.reimbursement !== 'owed' && <input type="checkbox" className="mt-1 h-4 w-4" checked={selected.includes(r.legacy_id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, r.legacy_id] : ids.filter(id => id !== r.legacy_id))}/>}<span>{r.description} · {usd(r.confirmation?.paid_amount || r.recorded_cost || '0')}</span></label><p className="text-slate-600">{r.owner_posting?.reason}</p></div>)}<p className="text-sm text-slate-600">Select only payments for which the business still owes you the full amount you paid.</p><div className="flex flex-wrap gap-2">{selected.length > 0 && <button type="button" disabled={busy} className={primary} onClick={confirmSelected}>Confirm {selected.length} payments still owed to me</button>}<Link className={secondary} to="/repairs">Review repair payments</Link>{rows.some(r => r.owner_posting?.status === 'ready') && <button type="button" className={primary} disabled={busy} onClick={postReady}>Record eligible reimbursements</button>}</div></div>}
    {notice && <p role="status" className="text-emerald-800">{notice}</p>}{error && <p role="alert" className="text-red-700">{error}</p>}
  </section>
}
