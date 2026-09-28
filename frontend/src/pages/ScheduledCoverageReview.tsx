import { useEffect, useState } from 'react'
import BankDialog from '../components/BankDialog'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'
import { bankProfilesApi } from '../services/api'

type Review = { id: number; limit_cents: number; source_name: string; destination_name: string; from_last4: string; to_last4: string; coverage: { charge?: {description:string; amount_cents:number; date:string; pending:boolean}; minimum_cents: number; possible_cents: number; pending_review_required: boolean } }
const money = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
export default function ScheduledCoverageReview({tenantId, draftId, onClose, onApproved}: {tenantId:number; draftId:string; onClose:()=>void; onApproved:()=>void}) {
  const [review, setReview] = useState<Review | null>(null)
  const [amount, setAmount] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void bankProfilesApi.request<Review>(tenantId, `/drafts/${draftId}/review`, 'post').then(({data}) => {
      if (!active) return
      setReview(data)
      if (!data.coverage.pending_review_required) setAmount(((data.coverage.charge?.amount_cents ?? Math.min(data.limit_cents, data.coverage.possible_cents)) / 100).toFixed(2))
    }).catch(e => { if (active) setError(e.response?.data?.detail || 'Could not refresh balances. Close this review and try again.') })
    return () => { active = false }
  }, [tenantId, draftId])
  let cents = 0
  try { cents = centsFromMoneyInput(amount) } catch { /* Keep approval disabled. */ }
  const approve = async () => {
    if (!review || !confirmed || saving) return
    setSaving(true); setError('')
    try {
      await bankProfilesApi.request(tenantId, `/reviews/${review.id}/draft`, 'post', {amount_cents:cents, coverage_confirmed:true})
      onApproved()
    } catch (e) {
      setError((e as {response?:{data?:{detail?:string}}}).response?.data?.detail || 'Could not approve this draft. Close and review again.')
    } finally { setSaving(false) }
  }
  return <BankDialog title="Review scheduled coverage" onClose={onClose}>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
    {!review && !error && <p role="status">Checking current balances…</p>}
    {review && <>
      <p className="font-medium">{review.source_name} · ••{review.from_last4} → {review.destination_name} · ••{review.to_last4}</p>
      {review.coverage.charge ? <div className="rounded-xl bg-blue-50 p-4"><p className="font-medium">{review.coverage.charge.description}</p><p className="mt-1 text-sm">{review.coverage.charge.date} · {review.coverage.charge.pending ? 'Pending' : 'Posted'}</p><p className="mt-2 text-xl font-semibold">{money(review.coverage.charge.amount_cents)}</p><p className="text-xs text-slate-600">Full charge · from available funding {money(review.limit_cents)}</p></div> : <dl className="grid grid-cols-2 gap-3 rounded-xl bg-blue-50 p-4 text-sm"><dt>Shortfall + reserve</dt><dd className="text-right font-semibold">{money(review.coverage.minimum_cents)}</dd><dt>Including additional pending debits</dt><dd className="text-right font-semibold">{money(review.coverage.possible_cents)}</dd><dt>Available from this source</dt><dd className="text-right font-semibold">{money(review.limit_cents)}</dd></dl>}
      {review.coverage.pending_review_required && <p className="text-sm text-slate-600">Pending debits may already affect the balance. Check Truliant and enter the amount needed.</p>}
      {!review.coverage.charge && <label className="block text-sm font-medium">Transfer amount<MoneyInput value={amount} onChange={v => {setAmount(v); setConfirmed(false)}} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>}
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} className="mt-1" />{review.coverage.charge ? 'This charge needs funding, has not already been covered, and I approve this transfer.' : 'I checked the balance and pending debits and approve this amount.'}</label>
      {review.coverage.charge && review.limit_cents < review.coverage.charge.amount_cents && <p role="alert" className="text-sm text-red-800">This source cannot cover the full charge now. Remove this unprepared draft, then select the charge and another source in Add a charge manually.</p>}
      <button type="button" disabled={saving || !confirmed || cents <= 0 || cents > Math.min(review.limit_cents, review.coverage.possible_cents)} onClick={() => void approve()} className="min-h-11 rounded-xl bg-blue-700 px-4 font-semibold text-white disabled:opacity-45">{saving ? 'Approving…' : 'Approve draft'}</button>
      <p className="text-xs text-slate-500">Next: prepare the bank form. You submit the transfer in Truliant.</p>
    </>}
  </BankDialog>
}
