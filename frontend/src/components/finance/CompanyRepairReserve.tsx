import {useEffect, useState} from 'react'
import {reserveApi, type CompanyRepairReserve as Pool} from '../../services/api'
import {repairMoney} from '../repairs/repairReview'

export default function CompanyRepairReserve({tenantId, refreshKey}: {tenantId?: number; refreshKey?: unknown}) {
  const [pool, setPool] = useState<Pool | null>(null)
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let active = true
    setPool(null); setFailed(false)
    if (tenantId) reserveApi.getPool().then(response => {if (active) setPool(response.data)}).catch(() => {if (active) setFailed(true)})
    return () => {active = false}
  }, [tenantId, refreshKey, reload])
  return <section className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4" aria-label="Shared company repair reserve">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-gray-900">Shared repair reserve</h2><p className="mt-1 text-sm text-gray-600">All trucks and trailers</p></div>
      <div className="text-right"><p className="text-xs text-gray-600">{pool ? `Through ${pool.as_of}` : failed ? 'Balance unavailable' : 'Loading shared balance…'}</p><p className={`text-xl font-semibold ${pool && Number(pool.fund.balance) < 0 ? 'text-red-700' : 'text-gray-900'}`}>{pool ? repairMoney(pool.fund.balance) : '—'}</p></div></div>
    {pool && <p className="mt-2 text-sm text-gray-700">Added {repairMoney(pool.fund.added)} · Used {repairMoney(pool.fund.used)} {Number(pool.fund.balance) < 0 ? ' Shared reserve is negative.' : ''}</p>}
    <details className="mt-2 text-xs text-gray-600"><summary className="min-h-8 cursor-pointer" aria-label="Shared reserve details">Details</summary><p>Contributions and repair payments since January 1, 2026. Equipment attribution is retained. Bank cash coverage is verified separately.</p></details>
    {failed && <button type="button" className="mt-2 min-h-11 text-sm text-blue-700" onClick={() => setReload(reload + 1)}>Retry shared reserve</button>}
  </section>
}
