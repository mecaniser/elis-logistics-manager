import type { Repair, ReserveBalance } from '../../services/api'
import { repairMoney } from './repairReview'

export default function EquipmentRepairHistory({ equipmentName, repairs, repairReserve, onReview }: { equipmentName: string; repairs: Repair[]; repairReserve?: ReserveBalance | null; onReview: (id: number) => void }) {
  const ordered = [...repairs].sort((a, b) => (b.repair_date || '').localeCompare(a.repair_date || '') || b.id - a.id)
  const total = repairs.reduce((sum, r) => sum + Number(r.cost || 0), 0)
  return <section className="mb-6 rounded-lg bg-white p-4 shadow sm:p-6" aria-label={`${equipmentName} repair history`}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-base font-semibold text-gray-900 sm:text-lg">Repairs &amp; Maintenance</h2><p className="mt-1 text-sm text-gray-600">{repairs.length} repair{repairs.length === 1 ? '' : 's'} assigned to this equipment.</p></div>
      <div className="text-right"><p className="text-xs text-gray-500">Repair costs</p><p className="text-xl font-semibold text-red-600">{repairMoney(String(total))}</p></div>
    </div>
    {repairReserve && (Number(repairReserve.deposits_total) !== 0 || Number(repairReserve.withdrawals_total) !== 0 || Number(repairReserve.adjustments_total) !== 0) && <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm"><p className="font-medium">Equipment contribution &amp; usage</p><dl className="mt-2 space-y-1">{[['Contributed', repairReserve.deposits_total], ...(Number(repairReserve.adjustments_total) !== 0 ? [['Adjustments', repairReserve.adjustments_total]] : []), ['Used', repairReserve.withdrawals_total], ['Net contribution', repairReserve.balance]].map(([label, value]) => <div key={label} className="flex flex-wrap justify-between gap-2"><dt>{label}</dt><dd>{repairMoney(String(value))}</dd></div>)}</dl></div>}
    <details className="mt-3 text-xs text-gray-600"><summary className="min-h-8 cursor-pointer" aria-label="Repair accounting details">Details</summary><p>These repairs also appear in Maintenance &amp; Repairs. Invoice costs and verified payments are reviewed separately. Net contribution is contributions plus adjustments minus usage for this equipment. Repairs use the shared company reserve; trailer replacement savings remain separate.</p></details>
    {ordered.length ? <ul className="mt-4 max-h-96 space-y-2 overflow-y-auto">{ordered.map(repair => <li key={repair.id} className="rounded-lg border border-gray-200 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-gray-900">{repair.title || repair.description || 'Repair'}</p><p className="mt-1 text-xs text-gray-500">{repair.repair_date ? new Date(`${repair.repair_date}T12:00:00`).toLocaleDateString() : 'Service date needs review'}{repair.invoice_number ? ` · Invoice ${repair.invoice_number}` : ''}</p></div><p className="font-semibold text-red-600">{repair.cost == null ? 'Cost needs review' : repairMoney(String(repair.cost))}</p></div>
      <button type="button" className="mt-2 min-h-11 text-sm text-blue-700 hover:underline" onClick={() => onReview(repair.id)}>Invoice &amp; payment review</button>
    </li>)}</ul> : <p className="mt-4 text-sm text-gray-500">No repairs have been recorded for this equipment yet.</p>}
  </section>
}
