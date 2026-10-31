import { useEffect, useRef, useState } from 'react'
import { dieselBridgeFinancialApi, type DieselBridgeFinancialPreviewRow } from '../../services/api'
import { financeError } from '../../services/finance'

export default function DieselBridgeEquipmentReview({ tenantId, slug, row, onSaved }: { tenantId: number; slug: string; row: DieselBridgeFinancialPreviewRow; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [assets, setAssets] = useState<{ id: number; name: string; vehicle_type: 'truck' | 'trailer'; vin: string | null }[]>([])
  const [assetId, setAssetId] = useState('')
  const [kind, setKind] = useState<'truck' | 'trailer'>('trailer')
  const [interim, setInterim] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = useRef(true)
  const request = useRef<{ body: string; key: string } | null>(null)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    if (!open) return
    let current = true
    dieselBridgeFinancialApi.equipmentOptions(tenantId).then(r => { if (current) setAssets(r.data.items) }).catch(e => { if (current) setError(financeError(e)) })
    return () => { current = false }
  }, [open, tenantId])
  if (row.repair_id || !row.source_revision || !row.invoice_id) return null
  const control = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50'
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!assetId || !row.source_revision || reason.trim().length < 3 || busy) return
    const body = { asset_id: Number(assetId), expected_source_revision: row.source_revision, work_equipment_type: kind, interim_unit_allocation: interim, ...(row.equipment_allocation ? { supersedes_id: row.equipment_allocation.id } : {}), reason: reason.trim() }
    const serialized = JSON.stringify(body)
    if (request.current?.body !== serialized) request.current = { body: serialized, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      await dieselBridgeFinancialApi.allocateEquipment(tenantId, slug, row.repair_order_id, body, request.current.key)
      if (active.current) { setOpen(false); onSaved() }
    } catch (e) { if (active.current) setError(financeError(e)) }
    finally { if (active.current) setBusy(false) }
  }
  return <div className="mt-2">
    {row.equipment_allocation && <p className="text-gray-600">Reviewed {row.equipment_allocation.work_equipment_type} work{row.equipment_allocation.interim_unit_allocation ? ' · temporarily assigned to the truck unit; trailer identity unresolved' : ''}. {row.equipment_allocation.reason}</p>}
    <button type="button" className={control} disabled={busy} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Close equipment review' : 'Review repair equipment'}</button>
    {open && <form className="mt-2 space-y-2 rounded border border-gray-200 bg-white p-3" onSubmit={save}>
      <p>Assign this entire invoice to the equipment that received the work. Existing imported repairs require a separate financial correction before moving equipment.</p>
      <label className="block">Work performed on<select className={`${control} block w-full`} disabled={busy} value={kind} onChange={e => { setKind(e.target.value as 'truck' | 'trailer'); setInterim(false) }}><option value="trailer">Trailer</option><option value="truck">Truck</option></select></label>
      <label className="block">Equipment receiving this cost<select className={`${control} block w-full`} required disabled={busy} value={assetId} onChange={e => setAssetId(e.target.value)}><option value="">Choose verified equipment</option>{assets.map(a => <option key={a.id} value={a.id}>{a.name} · {a.vehicle_type}{a.vin ? ` · ${a.vin}` : ' · VIN not recorded'}</option>)}</select></label>
      {kind === 'trailer' && <label className="flex min-h-11 items-start gap-2"><input className="mt-1" type="checkbox" disabled={busy} checked={interim} onChange={e => setInterim(e.target.checked)} /><span>Trailer identity is unresolved. Temporarily assign this trailer work to the selected truck unit.</span></label>}
      <label className="block">Evidence and reason<textarea className={`${control} block w-full`} required minLength={3} maxLength={2000} disabled={busy} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <p className="text-xs text-gray-600">Saves an audited equipment decision. It does not import the invoice, prove payment, move reserves, or grant historical access.</p>
      <button type="submit" className={control} disabled={busy || !assetId || reason.trim().length < 3}>Save equipment decision</button>
    </form>}
    {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
  </div>
}
