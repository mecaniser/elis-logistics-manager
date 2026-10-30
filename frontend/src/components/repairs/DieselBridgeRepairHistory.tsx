import { useEffect, useRef, useState } from 'react'
import { dieselBridgeApi, dieselBridgeHistoryApi, type DieselBridgeRepairHistoryRow } from '../../services/api'
import { historyDate, historyReviewMessage, historyTitle, sortHistory } from './dieselBridgeHistory'

type Connection = { slug: string }

export default function DieselBridgeRepairHistory({ tenantId, truckId, manageSync = true }: { tenantId?: number; truckId?: number; manageSync?: boolean }) {
  const [rows, setRows] = useState<DieselBridgeRepairHistoryRow[]>([])
  const [total, setTotal] = useState(0)
  const [after, setAfter] = useState<number | null>(null)
  const [connections, setConnections] = useState<Connection[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const scope = `${tenantId}:${truckId}:${manageSync}`
  const currentScope = useRef(scope)
  currentScope.current = scope
  const active = useRef(true)
  useEffect(() => {
    active.current = true
    return () => { active.current = false }
  }, [])
  useEffect(() => {
    let live = true
    setRows([]); setTotal(0); setAfter(null); setConnections([]); setError(''); setMessage(''); setLoading(true); setBusy(false)
    if (!tenantId) { setLoading(false); return }
    Promise.all([
      dieselBridgeHistoryApi.list(tenantId, truckId),
      manageSync ? dieselBridgeApi.connections(tenantId) : Promise.resolve({ data: { items: [] } }),
    ]).then(([history, configured]) => {
      if (!live) return
      setRows(history.data.items); setTotal(history.data.total); setAfter(history.data.next_after); setConnections(configured.data.items)
    }).catch(() => { if (live) setError('Unable to load DBN repair history. Check your access and try again.') })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [tenantId, truckId, manageSync])

  const isCurrent = (requestedScope: string) => active.current && currentScope.current === requestedScope
  const run = async (action: (requestedScope: string) => Promise<void>) => {
    const requestedScope = scope
    setBusy(true); setError(''); setMessage('')
    try { await action(requestedScope) } catch { if (isCurrent(requestedScope)) setError('The request could not be completed. Refresh the history and try again.') }
    finally { if (isCurrent(requestedScope)) setBusy(false) }
  }
  const refresh = async (requestedScope: string) => {
    if (!tenantId) return
    const response = await dieselBridgeHistoryApi.list(tenantId, truckId)
    if (isCurrent(requestedScope)) { setRows(response.data.items); setTotal(response.data.total); setAfter(response.data.next_after) }
  }
  const button = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600'
  return <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4 sm:p-6" aria-label="DBN repair order history" aria-busy={loading || busy}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">DBN repair history{!loading && ` (${total})`}</h2>
        <p className="mt-1 text-sm text-gray-600">Service dates and work summaries from DieselBridge. Saved repair costs and payment records are managed separately.</p>
      </div>
      <button className={button} disabled={busy || loading || !tenantId} onClick={() => run(refresh)}>Refresh history</button>
    </div>
    {manageSync && connections.map(connection => <div key={connection.slug} className="mt-4 flex flex-wrap items-center gap-2">
      <span className="mr-1 text-sm text-gray-600">{connection.slug.replace(/[-_]/g, ' ')}</span>
      <button className={button} disabled={busy || loading} onClick={() => run(async requestedScope => {
        const response = await dieselBridgeHistoryApi.sync(tenantId!, connection.slug, true)
        if (isCurrent(requestedScope)) setMessage(`Preview: ${response.data.source_count} repair orders, ${response.data.matched} matched to trucks, ${response.data.review_required} needing review. No records saved.`)
      })}>Preview repair orders</button>
      <button className={button} disabled={busy || loading} onClick={() => run(async requestedScope => {
        const response = await dieselBridgeHistoryApi.sync(tenantId!, connection.slug, false)
        await refresh(requestedScope)
        if (isCurrent(requestedScope)) setMessage(`History synced: ${response.data.source_count} source repair orders, ${response.data.created} added, ${response.data.updated} updated, ${response.data.unchanged} unchanged. ${response.data.review_required ? `${response.data.review_required} need review.` : ''}`)
      })}>Sync repair history</button>
    </div>)}
    {message && <p role="status" className="mt-3 text-sm text-gray-700">{message}</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {loading && <p className="mt-4 text-sm text-gray-600">Loading DBN repair history…</p>}
    {!loading && !error && !rows.length && <p className="mt-4 text-sm text-gray-600">{truckId ? 'No DBN repair orders are linked to this truck yet.' : 'No DBN repair orders have been imported yet.'}</p>}
    <ul className="mt-4 divide-y divide-gray-100">
      {sortHistory(rows).map(row => <li key={row.id} className="py-4 first:pt-0 last:pb-0">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="break-words font-medium text-gray-900">{historyTitle(row)}</h3>
          {row.service && <p className="text-sm text-gray-600">{row.service.service_date_source === 'created_at_fallback' ? 'Recorded' : 'Completed'} {historyDate(row.service.service_date)}</p>}
        </div>
        {row.service ? <>
          <p className="mt-1 text-sm text-gray-600">{row.truck_name || (row.truck_id ? `Truck #${row.truck_id}` : 'Truck assignment needs review')}{row.service.unit_number && ` · Source unit ${row.service.unit_number}`} · DBN status: {row.service.status}</p>
          {row.service.service_date_source === 'created_at_fallback' && <p className="mt-1 text-sm text-amber-800">Completion date unavailable; showing the source record date.</p>}
          <p className="mt-2 whitespace-pre-line break-words text-sm text-gray-700">{row.service.description || 'No work summary available.'}</p>
          {row.state === 'review_required' && <p className="mt-2 text-sm text-amber-800">{historyReviewMessage(row.review_reason)}</p>}
          {row.legacy_repair_candidates?.length > 0 && <p className="mt-2 text-sm text-gray-600">{row.legacy_repair_candidates.length} existing repair record{row.legacy_repair_candidates.length === 1 ? '' : 's'} on this service date. Review before adding costs; existing records were preserved.</p>}
        </> : <p className="mt-2 text-sm text-amber-800">This repair order is no longer available from the source. Its history reference is retained for review.</p>}
      </li>)}
    </ul>
    {after !== null && <button className={`${button} mt-4`} disabled={busy || loading} onClick={() => run(async requestedScope => {
      const response = await dieselBridgeHistoryApi.list(tenantId!, truckId, after)
      if (isCurrent(requestedScope)) { setRows(items => [...new Map([...items, ...response.data.items].map(row => [row.id, row])).values()]); setAfter(response.data.next_after); setTotal(response.data.total) }
    })}>Load more repair orders</button>}
  </section>
}
