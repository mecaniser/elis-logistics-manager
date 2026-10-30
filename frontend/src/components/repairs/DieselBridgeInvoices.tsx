import { useEffect, useState } from 'react'
import { dieselBridgeApi, type DieselBridgeInvoice } from '../../services/api'

type Connection = { slug: string; watermark: string | null; has_more: boolean }

export default function DieselBridgeInvoices({ tenantId, onAccepted }: { tenantId?: number; onAccepted: () => void }) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [invoices, setInvoices] = useState<DieselBridgeInvoice[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [after, setAfter] = useState<number | null>(null)
  useEffect(() => {
    let active = true
    setConnections([]); setInvoices([]); setMessage(''); setError(''); setSelected(null); setNote(''); setAfter(null)
    if (tenantId) Promise.all([dieselBridgeApi.connections(tenantId), dieselBridgeApi.invoices(tenantId)]).then(([c, i]) => {
      if (active) { setConnections(c.data.items); setInvoices(i.data.items); setAfter(i.data.next_after) }
    }).catch(() => { if (active) setError('Unable to load DieselBridge invoices. Check access and server configuration.') })
    return () => { active = false }
  }, [tenantId])
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('')
    try { await action() } catch { setError('The request could not be completed. Refresh and review the invoice or connection status.') }
    finally { setBusy(false) }
  }
  const refresh = async (tenant: number) => {
    const [c, i] = await Promise.all([dieselBridgeApi.connections(tenant), dieselBridgeApi.invoices(tenant)])
    setConnections(c.data.items); setInvoices(i.data.items); setAfter(i.data.next_after)
  }
  const pdf = (invoice: DieselBridgeInvoice) => run(async () => {
    const response = await dieselBridgeApi.pdf(tenantId!, invoice.id)
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a'); link.href = url; link.download = `dieselbridge-${invoice.id}.pdf`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  })
  return <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4" aria-label="DieselBridge invoices">
    <h2 className="text-lg font-semibold text-gray-900">DieselBridge repair invoices</h2>
    <p className="mt-1 text-sm text-gray-600">Review imported invoices before adding a repair cost. Payment and reserve use need separate confirmation.</p>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-gray-700">{message}</p>}
    {!connections.length && !error && <p className="mt-3 text-sm text-gray-600">No DieselBridge connection configured for this business.</p>}
    {connections.map(c => <div key={c.slug} className="mt-3 flex flex-wrap items-center gap-3 text-sm">
      <span>{c.slug} · {c.watermark ? `Synced through ${new Date(c.watermark).toLocaleString()}` : 'No completed sync'}</span>
      <button disabled={busy} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => run(async () => {
        const r = await dieselBridgeApi.sync(tenantId!, c.slug, true)
        setMessage(`Preview: ${r.data.items?.length || 0} invoices or scope events on this page. ${r.data.has_more ? 'More pages available.' : ''} No records saved.`)
      })}>Preview page</button>
      <button disabled={busy} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => run(async () => {
        const r = await dieselBridgeApi.sync(tenantId!, c.slug, false)
        await refresh(tenantId!)
        setMessage(`Saved ${r.data.applied} invoices or scope events. ${r.data.has_more ? 'Continue sync to fetch the next page.' : 'Sync complete.'}`)
      })}>{c.has_more ? 'Continue sync' : 'Sync invoices'}</button>
    </div>)}
    <ul className="mt-4 divide-y divide-gray-100">
      {invoices.map(i => <li key={i.id} className="py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><p className="font-medium">Invoice {i.invoice.invoice_number || i.invoice_id}{i.invoice.total_amount && ` · $${i.invoice.total_amount}`}</p>
            <p className="text-sm text-gray-600">{i.truck_id ? `Truck #${i.truck_id}` : 'Truck needs review'} · {i.invoice.vin || 'VIN unavailable'} · {i.review_reason.replace(/_/g, ' ')}</p>
            {i.repair_id && <p className="text-sm text-gray-600">Linked to repair #{i.repair_id}. {i.state !== 'accepted' && 'Review the existing repair and accounting entries before making a correction.'}</p>}
          </div>
          <div className="flex gap-2">
            {i.state !== 'access_removed' && <button disabled={busy} onClick={() => pdf(i)} className="rounded border px-3 py-2 text-sm">Invoice PDF</button>}
            {!i.repair_id && i.state === 'review_required' && ['cost_treatment_required', 'unmatched_vin', 'missing_vin', 'duplicate_vin', 'vehicle_type_mismatch'].includes(i.review_reason) && <button disabled={busy} onClick={() => { setSelected(i.id); setNote('') }} className="rounded border px-3 py-2 text-sm">Review cost</button>}
          </div>
        </div>
        {selected === i.id && <form className="mt-3 space-y-2" onSubmit={e => { e.preventDefault(); run(async () => {
          await dieselBridgeApi.accept(tenantId!, i.id, i.revision, note)
          setSelected(null); await refresh(tenantId!); onAccepted(); setMessage('Repair cost added. Payment remains unverified.')
        }) }}>
          <p className="text-sm">Confirm this invoice is a repair expense for the truck with this VIN. Vehicle matching is checked again when you save. Correct missing or duplicate VINs in Trucks first.</p>
          <label className="block text-sm">Review note<textarea required minLength={3} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} className="mt-1 block w-full rounded border p-2" /></label>
          <button disabled={busy} className="rounded bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50">Confirm repair expense</button>
          <button type="button" disabled={busy} onClick={() => setSelected(null)} className="ml-2 rounded border px-3 py-2 text-sm">Cancel</button>
        </form>}
      </li>)}
    </ul>
    {after !== null && <button disabled={busy} className="rounded border px-3 py-2 text-sm" onClick={() => run(async () => {
      const response = await dieselBridgeApi.invoices(tenantId!, after)
      setInvoices(items => [...items, ...response.data.items]); setAfter(response.data.next_after)
    })}>Load more invoices</button>}
  </section>
}
