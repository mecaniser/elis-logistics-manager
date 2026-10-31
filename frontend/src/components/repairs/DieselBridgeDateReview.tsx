import { useEffect, useRef, useState, type FormEvent } from 'react'
import { dieselBridgeReconciliationApi, type DieselBridgeFinancialPreviewRow } from '../../services/api'
import { financeError } from '../../services/finance'

export default function DieselBridgeDateReview({ tenantId, slug, row, onSaved }: { tenantId: number; slug: string; row: DieselBridgeFinancialPreviewRow; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [treatment, setTreatment] = useState<'confirmed_service_date' | 'source_default'>('confirmed_service_date')
  const [day, setDay] = useState(row.date_decision?.confirmed_service_date || '')
  const [note, setNote] = useState('')
  const [references, setReferences] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  const request = useRef<{ body: string; key: string } | null>(null)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  if (!row.source_revision || !row.invoice_id) return null
  const control = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50'
  async function save(event: FormEvent) {
    event.preventDefault()
    if (busy || !row.source_revision || note.trim().length < 3 || treatment === 'confirmed_service_date' && !day) return
    const body = { note: note.trim(), source_references: references.split('\n').map(v => v.trim()).filter(Boolean), date_treatment: treatment, expected_source_revision: row.source_revision, ...(treatment === 'confirmed_service_date' ? { confirmed_service_date: day } : {}), ...(row.date_decision ? { supersedes_note_id: row.date_decision.id } : {}) }
    const serialized = JSON.stringify(body)
    if (request.current?.body !== serialized) request.current = { body: serialized, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      await dieselBridgeReconciliationApi.appendSource(tenantId, slug, row.repair_order_id, body, request.current.key)
      if (active.current) { setOpen(false); onSaved() }
    } catch (e) { if (active.current) setError(financeError(e)) }
    finally { if (active.current) setBusy(false) }
  }
  return <div className="mt-2">
    {row.date_decision && <p className="text-gray-600">Date decision #{row.date_decision.id}: {row.date_decision.date_treatment === 'confirmed_service_date' ? row.date_decision.confirmed_service_date : 'DBN service completion, then invoice date'}. {row.date_decision.note}</p>}
    <button type="button" className={control} aria-expanded={open} disabled={busy} onClick={() => setOpen(!open)}>{open ? 'Close service date review' : 'Review service date'}</button>
    {open && <form onSubmit={save} className="mt-2 space-y-2 rounded border border-gray-200 bg-white p-3">
      <label className="block">Date treatment<select className={`${control} block w-full`} disabled={busy} value={treatment} onChange={e => setTreatment(e.target.value as typeof treatment)}><option value="confirmed_service_date">Use confirmed service completion date</option><option value="source_default">Use DBN completion date, then invoice date</option></select></label>
      {treatment === 'confirmed_service_date' && <label className="block">Confirmed service completion date<input type="date" className={`${control} block w-full`} required disabled={busy} value={day} onChange={e => setDay(e.target.value)} /></label>}
      <label className="block">Evidence and reason<textarea className={`${control} block w-full`} required minLength={3} maxLength={4000} disabled={busy} value={note} onChange={e => setNote(e.target.value)} /></label>
      <label className="block">Source references (one per line, up to 10)<textarea className={`${control} block w-full`} disabled={busy} value={references} onChange={e => setReferences(e.target.value)} /></label>
      <p className="text-xs text-gray-600">This audited decision controls the proposed repair and expense date. It preserves source dates and previous decisions. Imported repairs require a separate financial review; payment dates and reserves remain unchanged.</p>
      <button type="submit" className={control} disabled={busy || note.trim().length < 3 || treatment === 'confirmed_service_date' && !day}>Save reviewed date</button>
    </form>}
    {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
  </div>
}
