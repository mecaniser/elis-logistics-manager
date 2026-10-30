import { useEffect, useRef, useState } from 'react'
import { dieselBridgeFinancialApi, type DieselBridgeFinancialState, type DieselBridgeReplacementPlan } from '../../services/api'
import { financeError } from '../../services/finance'
import { repairMoney } from './repairReview'

export default function DieselBridgeReplacementReview({ tenantId, repairId, state, onSaved }: { tenantId: number; repairId: number; state: DieselBridgeFinancialState; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<{ id: number; title: string; date: string | null; cost: string | null }[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [day, setDay] = useState(localToday)
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [plan, setPlan] = useState<DieselBridgeReplacementPlan | null>(null)
  const [restoreId, setRestoreId] = useState<number | null>(null)
  const [digest, setDigest] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const request = useRef<{ body: string; key: string } | null>(null)
  // The parent keys this component by tenant, repair and source revision.
  const mountedTenant = useRef(tenantId)
  const valid = () => active.current && mountedTenant.current === tenantId
  const control = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50'
  function invalidate() { setPlan(null); setDigest(''); setConfirmed(false) }
  async function start(operationId: number | null = null) {
    setOpen(true); setRestoreId(operationId); setSelected([]); setReason(''); invalidate(); setError(''); setBusy(true)
    try {
      if (operationId === null) {
        const response = await dieselBridgeFinancialApi.replacementCandidates(tenantId, repairId)
        if (valid()) setItems(response.data.items)
      }
    } catch (e) { if (valid()) setError(financeError(e)) }
    finally { if (valid()) setBusy(false) }
  }
  async function preview() {
    setBusy(true); setError(''); setConfirmed(false)
    try {
      if (restoreId !== null) {
        const r = await dieselBridgeFinancialApi.replacementRestorePreview(tenantId, state.connection_slug, restoreId, day)
        if (valid()) { setPlan(r.data.original_operation.plan); setDigest(r.data.plan_digest) }
      } else {
        const r = await dieselBridgeFinancialApi.replacementPreview(tenantId, state.connection_slug, { repair_order_id: state.repair_order_id, legacy_repair_ids: selected, correction_date: day })
        if (valid()) { setPlan(r.data); setDigest(r.data.plan_digest) }
      }
    } catch (e) { if (valid()) { setPlan(null); setError(financeError(e)) } }
    finally { if (valid()) setBusy(false) }
  }
  async function save() {
    if (!plan || !digest || !confirmed || reason.trim().length < 3 || busy) return
    const body = { correction_date: day, expected_plan_digest: digest, reviewed_existing_effects: true, reason: reason.trim(), ...(restoreId === null ? { repair_order_id: state.repair_order_id, legacy_repair_ids: selected, confirmed_same_job: true } : {}) }
    const identity = JSON.stringify({ restoreId, body })
    if (request.current?.body !== identity) request.current = { body: identity, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      if (restoreId !== null) await dieselBridgeFinancialApi.replacementRestore(tenantId, state.connection_slug, restoreId, body, request.current.key)
      else await dieselBridgeFinancialApi.replacementApply(tenantId, state.connection_slug, body, request.current.key)
      if (valid()) { setOpen(false); invalidate(); onSaved() }
    } catch (e) { if (valid()) setError(financeError(e)) }
    finally { if (valid()) setBusy(false) }
  }
  if (state.state !== 'active') return null
  return <div className="mt-3">
    <button className={control} type="button" disabled={busy} onClick={() => { void start() }}>Review temporary duplicates</button>
    {(state.temporary_replacements || []).map(op => <p key={op.id} className="mt-2">Replacement review #{op.id}: {op.reason} · {op.restored ? 'restored; audit retained' : 'temporary records archived'}{!op.restored && <button className={`${control} ml-2`} type="button" disabled={busy} onClick={() => { void start(op.id) }}>Review undo</button>}</p>)}
    {open && <div className="mt-2 space-y-2 rounded border border-gray-200 p-3">
      <p className="font-medium">{restoreId === null ? 'Replace temporary records with this DBN repair' : `Undo replacement review #${restoreId}`}</p>
      <p>Original records and evidence are retained. Only the reviewed existing bookkeeping entries are corrected. This does not record a payment or move cash.</p>
      {restoreId !== null && <p className="text-amber-800">Undo restores the state before replacement, including temporary costs and withdrawals. This DBN repair stays active, so duplicate expenses can reappear until reviewed again.</p>}
      <label className="block">Bookkeeping correction date<input className={`${control} block w-full`} type="date" max={localToday()} value={day} disabled={busy} onChange={e => { setDay(e.target.value); invalidate() }} /></label>
      {restoreId === null && <div>{items.length === 0 && <p>No eligible temporary records on this equipment.</p>}{items.map(x => <label key={x.id} className="flex min-h-11 items-start gap-2"><input className="mt-1" type="checkbox" disabled={busy} checked={selected.includes(x.id)} onChange={e => { setSelected(ids => e.target.checked ? [...ids, x.id] : ids.filter(id => id !== x.id)); invalidate() }} /><span>#{x.id} · {x.title} · {x.date || 'date unknown'} · {x.cost === null ? 'cost not recorded' : repairMoney(x.cost)}</span></label>)}</div>}
      <button className={control} type="button" disabled={busy || !day || (restoreId === null && !selected.length)} onClick={() => { void preview() }}>Preview existing effects</button>
      {plan && <div className="space-y-2"><p>Temporary costs {restoreId === null ? 'removed' : 'restored'}: {repairMoney(plan.expense_removed)}. Existing reserve withdrawals {restoreId === null ? 'reversed' : 'restored'}: {repairMoney(plan.reserve_correction)}.</p>
        {plan.temporary_records.map(x => <div key={x.repair.id} className="rounded bg-gray-50 p-2"><p>#{x.repair.id} · {x.repair.title || x.repair.description || 'Untitled repair'} · {x.repair.repair_date || 'date unknown'}</p>{x.withdrawals.map(w => <p key={w.id}>Reserve entry #{w.id} · {w.entry_date} · {repairMoney(w.amount)}</p>)}{x.journals.map(j => <div key={j.entry.id}><p>Journal #{j.entry.id} · {j.entry.entry_date}</p>{j.lines.map((line, i) => <p key={i}>Account #{line.account_id}: debit {repairMoney(line.debit)}, credit {repairMoney(line.credit)}</p>)}</div>)}</div>)}
        <label className="block">Review reason<textarea className={`${control} block w-full`} required minLength={3} maxLength={500} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label>
        <label className="flex min-h-11 items-start gap-2"><input className="mt-1" type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} /><span>{restoreId === null ? 'I confirmed these are temporary records for this same job and reviewed every existing bookkeeping effect above.' : 'I reviewed this undo and the restored costs and bookkeeping effects.'}</span></label>
        <button className={control} type="button" disabled={busy || !confirmed || reason.trim().length < 3} onClick={() => { void save() }}>{restoreId === null ? 'Archive reviewed duplicates' : 'Restore reviewed temporary records'}</button>
      </div>}
      <button className={control} type="button" disabled={busy} onClick={() => setOpen(false)}>Close replacement review</button>
    </div>}
    {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
  </div>
}
function localToday() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
