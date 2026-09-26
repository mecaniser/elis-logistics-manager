import { useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'

type Route = { kind: 'checking' | 'repayment'; from_last4: string; to_last4: string; amount_cents: number }
type Cash = { last4: string; nickname: string; current_cents: number | null; available_cents: number | null; reported_pending_cents: number | null; queued_cents: number; reserve_cents: number; limit_cents: number | null }
type Review = { id: number; expires_at: string; result: { observed_at: string; cash_accounts: Cash[]; credit_accounts: { last4: string; nickname: string; owed_cents: number | null }[]; proposals: Route[]; issues: string[]; transaction_feed_status: string; last_transaction_update: string | null } }
const money = (value: number | null) => value === null ? 'Unavailable' : (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const errorText = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : 'Unable to refresh this review. Try again.'
}

export default function BankTransferReview({ tenantId, onClose, onCreated }: { tenantId: number; onClose: () => void; onCreated: (count: number) => void }) {
  const [review, setReview] = useState<Review | null>(null)
  const [amounts, setAmounts] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [now, setNow] = useState(Date.now())
  const alive = useRef(true)
  const initial = useRef(false)
  const panel = useRef<HTMLElement>(null)
  const close = useRef(onClose)
  close.current = () => { if (!saving) onClose() }
  const refresh = async () => {
    setLoading(true); setError(''); setReview(null)
    try {
      const response = await bankMonitorApi.transferReview(tenantId)
      if (!alive.current) return
      const value = response.data as Review
      setReview(value); setAmounts(value.result.proposals.map(p => (p.amount_cents / 100).toFixed(2))); setNow(Date.now())
    } catch (error) { if (alive.current) setError(errorText(error)) }
    finally { if (alive.current) setLoading(false) }
  }
  useEffect(() => {
    alive.current = true
    if (!initial.current) { initial.current = true; void refresh() }
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current()
      if (event.key !== 'Tab') return
      const elements = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), summary, [tabindex="0"]')
      if (!elements?.length) return
      const first = elements[0], last = elements[elements.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    document.addEventListener('keydown', keydown)
    return () => { alive.current = false; document.body.style.overflow = overflow; document.removeEventListener('keydown', keydown); window.clearInterval(timer); previous?.focus() }
    // A new tenant mounts a new review; do not refetch when parent callbacks change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId])
  const values = amounts.map(value => { try { return centsFromMoneyInput(value) } catch { return -1 } })
  const invalid = values.some((value, index) => value < 0 || value > (review?.result.proposals[index].amount_cents ?? 0))
  const selected = review?.result.proposals.filter((_, index) => values[index] > 0) || []
  const expired = Boolean(review && now >= Date.parse(review.expires_at))
  const names = Object.fromEntries([...(review?.result.cash_accounts || []), ...(review?.result.credit_accounts || [])].map(a => [a.last4, a.nickname]))
  const retainedCash = (suffix: string) => {
    const account = review?.result.cash_accounts.find(a => a.last4 === suffix)
    if (!account || account.limit_cents === null) return null
    const chosen = review!.result.proposals.reduce((sum, route, index) => sum + (route.from_last4 === suffix ? Math.max(0, values[index] || 0) : 0), 0)
    return Math.max(0, account.limit_cents + account.reserve_cents - chosen)
  }
  const create = async () => {
    if (!review || invalid || expired || !selected.length) return
    setSaving(true); setError('')
    try {
      const routes = review.result.proposals.flatMap((route, index) => values[index] > 0 ? [{ from_last4: route.from_last4, to_last4: route.to_last4, amount_cents: values[index] }] : [])
      const response = await bankMonitorApi.createReviewedTransfers(tenantId, review.id, routes)
      if (alive.current) onCreated(response.data.created)
    } catch (error) { if (alive.current) setError(errorText(error)) }
    finally { if (alive.current) setSaving(false) }
  }
  return <div className="fixed inset-0 z-50">
    <div className="absolute inset-0 bg-slate-950/45" onClick={() => { if (!saving) onClose() }} />
    <section ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="transfer-review-title" className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col bg-white shadow-2xl outline-none">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 p-5 sm:px-7">
        <div><p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Transfer review</p><h2 id="transfer-review-title" className="mt-1 text-xl font-semibold text-slate-950">Choose your transfers</h2><p className="mt-2 text-sm leading-6 text-slate-600">Review the prefilled amounts. You submit each transfer in Truliant.</p></div>
        <button type="button" aria-label="Close transfer review" disabled={saving} onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-2xl text-slate-600 hover:bg-slate-100 focus-visible:outline-blue-600">×</button>
      </header>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5 sm:p-7" aria-busy={loading}>
        {loading && <div role="status" className="rounded-xl bg-blue-50 p-6 text-sm leading-6 text-blue-900"><p className="font-semibold">Refreshing bank balances…</p><p>Reading Plaid and calculating transfers after reserves and unfinished drafts. This can take a moment.</p></div>}
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</p>}
        {review && <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500"><span>Bank balances read {new Date(review.result.observed_at).toLocaleTimeString()}</span><button type="button" disabled={saving} onClick={() => void refresh()} className="min-h-11 rounded-lg px-3 font-semibold text-blue-700 hover:bg-blue-50">Refresh data</button></div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><p className="font-semibold">Based on bank-reported balances</p><p>Pending feeds may omit payments. Keep cash for upcoming bills; these are repayment estimates, not payoff quotes.</p>{review.result.transaction_feed_status !== 'observed' && <p className="mt-2 font-medium">Transaction details are unavailable in this read.</p>}</div>
          {review.result.issues.map(issue => <p key={issue} role="status" className="rounded-xl bg-slate-100 p-4 text-sm leading-6 text-slate-700">{issue}</p>)}
          <fieldset disabled={saving} className="min-w-0 space-y-4">{review.result.proposals.map((route, index) => <article key={`${route.from_last4}-${route.to_last4}`} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">{route.kind === 'checking' ? 'Checking coverage' : 'Credit repayment'}</p>
            <p className="mt-3 text-sm font-medium text-slate-950">{names[route.from_last4]} · ••{route.from_last4}</p><p className="mt-1 text-sm text-slate-600">→ {names[route.to_last4]} · ••{route.to_last4}</p>
            <label className="mt-4 block text-sm font-medium text-slate-700">Transfer amount for ••{route.from_last4} to ••{route.to_last4}<MoneyInput value={amounts[index]} onChange={value => setAmounts(current => current.map((old, i) => i === index ? value : old))} invalid={values[index] < 0 || values[index] > route.amount_cents} describedBy={`route-limit-${index}`} className="min-h-12 w-full rounded-xl border border-slate-300 px-3 text-lg font-semibold tabular-nums focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-100" /></label>
            <p id={`route-limit-${index}`} className={`mt-2 text-xs ${values[index] < 0 || values[index] > route.amount_cents ? 'text-red-700' : 'text-slate-500'}`}>Up to {money(route.amount_cents)} from this allocation.</p><p className="mt-2 text-xs text-emerald-800">Estimated cash kept in ••{route.from_last4} after all selected drafts: {money(retainedCash(route.from_last4))}, including your reserve.</p><button type="button" onClick={() => setAmounts(current => current.map((value, i) => i === index ? values[index] === 0 ? (route.amount_cents / 100).toFixed(2) : '0.00' : value))} className="mt-1 min-h-11 rounded-lg px-2 text-xs font-semibold text-blue-700 hover:bg-blue-50">{values[index] === 0 ? 'Restore suggested amount' : 'Skip this transfer'}</button>
          </article>)}</fieldset>
          <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-800">How much cash is protected?</summary><div className="mt-4 space-y-5">{review.result.cash_accounts.map(account => {
            const chosen = review.result.proposals.reduce((sum, route, index) => sum + (route.from_last4 === account.last4 ? Math.max(0, values[index] || 0) : 0), 0)
            return <div key={account.last4}><p className="text-sm font-semibold text-slate-900">{account.nickname} · ••{account.last4}</p><dl className="mt-2 grid grid-cols-2 gap-3 text-xs text-slate-600">{[['Posted', account.current_cents], ['Bank available', account.available_cents], ['Pending debits reported', account.reported_pending_cents], ['Reserve protected', account.reserve_cents], ['Already in queue', account.queued_cents], ['Review limit', account.limit_cents], ['Unallocated after these drafts', account.limit_cents === null ? null : Math.max(0, account.limit_cents - chosen)]].map(([label, amount]) => <div key={String(label)}><dt>{label}</dt><dd className="mt-1 font-semibold tabular-nums text-slate-900">{money(amount as number | null)}</dd></div>)}</dl></div>
          })}<p className="text-xs leading-5 text-slate-500">The limit uses the lowest of posted cash, bank-available cash and posted cash less reported pending debits. Reserves and unfinished outgoing drafts are then protected. Holds are not subtracted twice.</p>{review.result.last_transaction_update && <p className="text-xs text-slate-500">Transaction feed updated {new Date(review.result.last_transaction_update).toLocaleString()}.</p>}</div></details>
          {!review.result.proposals.length && <p className="rounded-xl bg-slate-50 p-5 text-sm text-slate-700">No new transfer is available after protecting your reserve and unfinished transfers.</p>}
          {expired && <p role="status" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">This five-minute review expired. Refresh balances to continue.</p>}
        </>}
      </div>
      <footer className="shrink-0 border-t border-slate-200 bg-white p-5 sm:px-7"><p className="mb-3 text-xs leading-5 text-slate-500">Creating drafts does not move money. ELIS checks balances again before preparing the bank form.</p>{expired ? <button type="button" disabled={saving} onClick={() => void refresh()} className="min-h-12 w-full rounded-xl bg-blue-700 px-4 font-semibold text-white">Refresh review</button> : !review && !loading ? <button type="button" onClick={() => void refresh()} className="min-h-12 w-full rounded-xl bg-blue-700 px-4 font-semibold text-white">Try bank refresh again</button> : <button type="button" disabled={loading || saving || invalid || expired || !selected.length} onClick={() => void create()} className="min-h-12 w-full rounded-xl bg-blue-700 px-4 font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-45">{saving ? 'Creating drafts…' : `Create ${selected.length || ''} reviewed transfer${selected.length === 1 ? '' : 's'}`}</button>}</footer>
    </section>
  </div>
}
