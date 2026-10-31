import { useEffect, useRef, useState } from 'react'
import { dieselBridgeApi, dieselBridgeFinancialApi, type DieselBridgeFinancialPreview } from '../../services/api'
import { financeError } from '../../services/finance'
import { financialReviewMessage, previewCounts } from './dieselBridgeFinancial'
import { repairMoney } from './repairReview'
import DieselBridgeDateReview from './DieselBridgeDateReview'
import DieselBridgeEquipmentReview from './DieselBridgeEquipmentReview'

export default function DieselBridgeFinancialSync({ tenantId, onSaved }: { tenantId?: number; onSaved: () => void }) {
  const [connections, setConnections] = useState<{ slug: string }[]>([])
  const [previews, setPreviews] = useState<Record<string, DieselBridgeFinancialPreview>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const scope = useRef(tenantId)
  const active = useRef(true)
  const requestKeys = useRef(new Map<string, string>())
  scope.current = tenantId
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    let current = true
    setConnections([]); setPreviews({}); setBusy(null); setMessage(''); setError(''); requestKeys.current.clear()
    if (tenantId) dieselBridgeApi.connections(tenantId).then(response => {
      if (current) setConnections(response.data.items)
    }).catch(() => { if (current) setError('Could not check the DBN connection. Refresh Invoice review and try again.') })
    return () => { current = false }
  }, [tenantId])
  const isCurrent = (tenant: number) => active.current && scope.current === tenant
  const control = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600'
  async function preview(slug: string) {
    if (!tenantId) return
    const tenant = tenantId
    setBusy(slug); setError(''); setMessage('')
    try {
      const response = await dieselBridgeFinancialApi.preview(tenant, slug)
      if (isCurrent(tenant)) setPreviews(items => ({ ...items, [slug]: response.data }))
    } catch (e) { if (isCurrent(tenant)) setError(importError(e)) }
    finally { if (isCurrent(tenant)) setBusy(null) }
  }
  async function sync(slug: string) {
    if (!tenantId || !previews[slug]?.executable) return
    const tenant = tenantId
    const digest = previews[slug].plan_digest
    const identity = `${tenant}:${slug}:${digest}`
    if (!requestKeys.current.has(identity)) requestKeys.current.set(identity, crypto.randomUUID())
    setBusy(slug); setError(''); setMessage('')
    try {
      const response = await dieselBridgeFinancialApi.sync(tenant, slug, digest, requestKeys.current.get(identity)!)
      if (!isCurrent(tenant)) return
      setPreviews(items => { const next = { ...items }; delete next[slug]; return next })
      setMessage(`DBN invoices imported: ${response.data.created} repairs added, ${response.data.unchanged} unchanged, ${response.data.review_required} needing review. Payment and reserve withdrawals follow verified recorded payments.`)
      onSaved()
    } catch (e) { if (isCurrent(tenant)) setError(importError(e)) }
    finally { if (isCurrent(tenant)) setBusy(null) }
  }
  if (!connections.length && !error) return null
  return <div className="mt-4 rounded-md border border-gray-200 bg-gray-50 p-3" aria-label="DBN invoice integration" aria-busy={busy !== null}>
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-gray-900">DBN invoices</p><button type="button" className={control} disabled={busy !== null} onClick={onSaved}>Refresh repair tiles</button></div>
    <p className="mt-1 text-sm text-gray-600">Finalized invoices become individual repair tiles below. Costs use service dates; reserve withdrawals follow verified recorded payments.</p>
    {connections.map(connection => {
      const result = previews[connection.slug]
      const counts = result ? previewCounts(result) : null
      return <div key={connection.slug} className="mt-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-600">{connection.slug.replace(/[-_]/g, ' ')}</span>
          <button type="button" className={control} disabled={busy !== null} onClick={() => preview(connection.slug)}>Preview DBN invoices</button>
          {result?.executable && <button type="button" className={`${control} bg-white text-blue-700`} disabled={busy !== null} onClick={() => sync(connection.slug)}>Import reviewed invoices</button>}
        </div>
        {result && counts && <div className="mt-3 text-sm">
          <p role="status">Preview: {result.source_count} source repair orders · {counts.create} new · {counts.unchanged} unchanged · {counts.review_required + counts.blocked} needing review. No records saved.</p>
          {!result.executable && <p className="mt-2 font-medium text-amber-800">Import is blocked until the invoice access and reconciliation issues below are resolved. Existing repair costs and payments are preserved.</p>}
          {Array.from(new Set(result.blockers.map(financialReviewMessage))).map(message => <p key={message} className="mt-1 text-amber-800">{message}</p>)}
          <details className="mt-2"><summary className="min-h-11 cursor-pointer py-2 text-blue-700">Review individual invoices ({result.rows.length})</summary>
            <ul className="divide-y divide-gray-200">{result.rows.map((row, index) => <li key={row.repair_order_id} className="py-2">
              <p className="font-medium">{row.order_number || `Repair order ${index + 1}`}{row.truck_name ? ` · ${row.truck_name}` : ''}</p>
              <p>{row.invoice_total === null ? 'Bookable amount unavailable; resolve source access or settlement review.' : `Proposed repair cost ${repairMoney(row.invoice_total)} · ${row.repair_date || 'Service date needs review'}`}</p>
              {row.source_invoice_total != null && <p className="text-gray-600">DBN quoted invoice total: {repairMoney(row.source_invoice_total)}</p>}
              {row.price_basis === 'settlement_principal_plus_applied_card_fees' && <p className="text-xs text-gray-600">Cost includes the full settlement principal and actual applied card fees, excluding uncharged quoted fees.</p>}
              {row.action === 'unchanged' && <p>Already imported; no change.</p>}
              {row.action === 'create' && <p>Will add one repair tile.</p>}
              {row.blockers.map(reason => <p key={reason} className="text-amber-800">{financialReviewMessage(reason)}</p>)}
              {tenantId && <DieselBridgeDateReview key={`date:${tenantId}:${connection.slug}:${row.repair_order_id}:${result.plan_digest}`} tenantId={tenantId} slug={connection.slug} row={row} onSaved={() => { void preview(connection.slug) }} />}
              {tenantId && <DieselBridgeEquipmentReview key={`${tenantId}:${connection.slug}:${row.repair_order_id}:${result.plan_digest}`} tenantId={tenantId} slug={connection.slug} row={row} onSaved={() => { void preview(connection.slug) }} />}
            </li>)}</ul>
          </details>
        </div>}
      </div>
    })}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-gray-700">{message}</p>}
  </div>
}
function importError(error: unknown): string {
  const response = (error as { response?: { status?: number } })?.response
  return response?.status === 503 ? 'DBN financial import is not enabled yet. Existing repair records are unchanged.' : financeError(error)
}
