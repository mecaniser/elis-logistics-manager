import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTenant } from '../../contexts/tenantState'
import { dieselBridgeReconciliationApi, type DieselBridgeFinancialState, type DieselBridgeReconciliationNote } from '../../services/api'
import { financeError } from '../../services/finance'
import { emptyReconciliationDraft, mergeReconciliationNotes, nextReconciliationCursor, reconciliationInput } from './reconciliationNotes'

export default function DieselBridgeReconciliationNotes({ repairId, state, onSaved }: { repairId: number; state: DieselBridgeFinancialState; onSaved: () => void }) {
  const { currentTenant } = useTenant()
  const tenantId = currentTenant?.id
  const scope = `${tenantId}:${repairId}:${state.repair_order_id}`
  const currentScope = useRef(scope)
  currentScope.current = scope
  const mounted = useRef(true)
  const keys = useRef(new Map<string, string>())
  const [saved, setSaved] = useState<{ scope: string; notes: DieselBridgeReconciliationNote[]; complete: boolean }>({ scope, notes: [], complete: false })
  const [draft, setDraft] = useState(emptyReconciliationDraft)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    setDraft(emptyReconciliationDraft()); setOpen(false); setBusy(false); setError(''); setMessage(''); keys.current.clear()
    setSaved({ scope, notes: [], complete: false })
  }, [scope])
  const current = (requested: string) => mounted.current && currentScope.current === requested
  const local = saved.scope === scope ? saved.notes : []
  const notes = mergeReconciliationNotes(state.repair_order_id, local, state.reconciliation_notes || [])
  const complete = saved.scope === scope && saved.complete
  const corrected = new Set(notes.map(note => note.supersedes_note_id).filter(Boolean))
  const input = reconciliationInput(draft)
  const control = 'mt-1 block min-h-11 w-full rounded border border-gray-300 bg-white px-3 py-2 text-base focus-visible:outline-blue-600'
  const button = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600'
  async function loadHistory() {
    if (!tenantId || busy) return
    const requested = scope
    setBusy(true); setError('')
    try {
      let after = 0
      const seen = new Set<number>()
      let collected: DieselBridgeReconciliationNote[] = []
      for (let page = 0; page < 200; page++) {
        const { data } = await dieselBridgeReconciliationApi.list(tenantId, repairId, after)
        if (!current(requested)) return
        collected = mergeReconciliationNotes(state.repair_order_id, collected, data.items)
        const next = nextReconciliationCursor(after, data.next_after, seen)
        if (next === null) {
          setSaved(previous => ({ scope: requested, notes: mergeReconciliationNotes(state.repair_order_id, previous.scope === requested ? previous.notes : [], collected), complete: true }))
          return
        }
        seen.add(next); after = next
      }
      throw new Error('Reconciliation history is too large to load in one request. Contact support to review the complete audit history.')
    } catch (failure) { if (current(requested)) setError(financeError(failure)) }
    finally { if (current(requested)) setBusy(false) }
  }
  async function append(event: FormEvent) {
    event.preventDefault()
    if (!tenantId || !input || busy) return
    const requested = scope
    const fingerprint = `${scope}:${JSON.stringify(input)}`
    if (!keys.current.has(fingerprint)) keys.current.set(fingerprint, crypto.randomUUID())
    setBusy(true); setError(''); setMessage('')
    try {
      const { data } = await dieselBridgeReconciliationApi.append(tenantId, repairId, input, keys.current.get(fingerprint)!)
      if (!current(requested)) return
      setSaved(previous => ({ scope: requested, notes: mergeReconciliationNotes(state.repair_order_id, previous.scope === requested ? previous.notes : [], notes, [data]), complete: previous.scope === requested && previous.complete }))
      keys.current.delete(fingerprint)
      setDraft(emptyReconciliationDraft()); setOpen(false)
      setMessage('Reconciliation note saved. Previous notes are retained.'); onSaved()
    } catch (failure) { if (current(requested)) setError(financeError(failure)) }
    finally { if (current(requested)) setBusy(false) }
  }
  return <section className="mt-3 rounded border border-gray-200 bg-gray-50 p-3" aria-label="Repair reconciliation notes" aria-busy={busy}>
    <h4 className="font-semibold text-gray-900">Reconciliation notes</h4>
    <p className="mt-1 text-xs text-gray-600">Source references, date decisions and amount differences stay with this repair through future syncs. Dates and amounts in notes are reference only; saving a note does not change repair costs, dates, payments or reserve withdrawals.</p>
    {!notes.length && <p className="mt-2 text-gray-600">No reconciliation notes recorded.</p>}
    {!!notes.length && <ol className="mt-3 space-y-3">{notes.map(note => <li key={note.id} className="rounded border border-gray-200 bg-white p-3">
      <p className="text-xs text-gray-600">Note #{note.id} · {note.created_at} · {note.author}</p>
      {note.supersedes_note_id && <p className="mt-1 text-xs font-medium text-amber-900">Correction to note #{note.supersedes_note_id}; original retained.</p>}
      {corrected.has(note.id) && <p className="mt-1 text-xs font-medium text-amber-900">Later correction recorded; retained for audit.</p>}
      <p className="mt-2 whitespace-pre-wrap break-words">{note.note}</p>
      {!!note.source_references.length && <div className="mt-2"><p className="text-xs font-medium">Source references</p><ul className="list-inside list-disc space-y-1">{note.source_references.map((reference, index) => <li key={index} className="whitespace-pre-wrap break-words">{reference}</li>)}</ul></div>}
      {note.confirmed_service_date && <p className="mt-2">Confirmed service date (note): {note.confirmed_service_date}</p>}
      {note.original_invoice_date && <p className="mt-1">Original invoice creation date (note): {note.original_invoice_date}</p>}
      {note.amount_discrepancy && <p className="mt-2 whitespace-pre-wrap break-words"><span className="font-medium">Amount discrepancy: </span>{note.amount_discrepancy}</p>}
    </li>)}</ol>}
    {state.reconciliation_notes_has_older && !complete && <button type="button" className={`${button} mt-3 bg-white text-blue-700`} disabled={busy} onClick={loadHistory}>Load complete note history</button>}
    <button type="button" className={`${button} mt-3 bg-white text-blue-700`} aria-expanded={open} disabled={busy || !tenantId} onClick={() => { setOpen(!open); setError(''); setMessage('') }}>{open ? 'Close note form' : 'Add reconciliation note'}</button>
    {open && <form onSubmit={append} className="mt-3 space-y-3">
      <label className="block">Reconciliation note<textarea className={control} required minLength={3} maxLength={4000} disabled={busy} value={draft.note} onChange={event => setDraft({ ...draft, note: event.target.value })} /></label>
      <label className="block">Source references (one per line, up to 10)<textarea className={control} disabled={busy} value={draft.references} onChange={event => setDraft({ ...draft, references: event.target.value })} placeholder="DBN invoice000021; ETSINV-1183; owner confirmation" /></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">Confirmed service date (optional)<input className={control} type="date" disabled={busy} value={draft.serviceDate} onChange={event => setDraft({ ...draft, serviceDate: event.target.value })} /></label>
        <label className="block">Original invoice creation date (optional)<input className={control} type="date" disabled={busy} value={draft.invoiceDate} onChange={event => setDraft({ ...draft, invoiceDate: event.target.value })} /></label>
      </div>
      <label className="block">Amount discrepancy and unresolved details (optional)<textarea className={control} maxLength={1000} disabled={busy} value={draft.discrepancy} onChange={event => setDraft({ ...draft, discrepancy: event.target.value })} /></label>
      <label className="block">Corrects an earlier note (optional)<select className={control} disabled={busy} value={draft.supersedes} onChange={event => setDraft({ ...draft, supersedes: event.target.value })}><option value="">New note</option>{notes.filter(note => !corrected.has(note.id)).map(note => <option key={note.id} value={note.id}>Note #{note.id}: {note.note.slice(0, 80)}</option>)}</select></label>
      {draft.note && !input && <p className="text-red-700">Use a note of 3–4000 characters, up to 10 references of 300 characters each, valid dates, and at most 1000 discrepancy characters.</p>}
      <p className="text-xs text-gray-600">Corrections append a new entry. Original notes cannot be edited or deleted. Notes do not approve invoice access or prove a payment.</p>
      <button type="submit" className={`${button} bg-white text-blue-700`} disabled={busy || !input}>Save reconciliation note</button>
    </form>}
    {error && <p role="alert" className="mt-3 text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-gray-700">{message}</p>}
  </section>
}
