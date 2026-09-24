import { useState } from 'react'
import { Link } from 'react-router-dom'
import { financeApi, financeError } from '../../services/finance'
import { repairMoney, reviewIssueLabels, matchesReview } from './repairReview'
import type { RepairReviewRow } from './repairReview'

export default function RepairEvidence({ row }: { row: RepairReviewRow }) {
  const [open, setOpen] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [error, setError] = useState('')
  async function download(id: string, media: string) {
    setError(''); setDownloading(id)
    try {
      const extension = ({'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'} as Record<string, string>)[media] || 'bin'
      await financeApi.download(`/evidence/${encodeURIComponent(id)}/original`, `repair-${row.legacy_id}-${id}.${extension}`)
    } catch (e) { setError(financeError(e)) }
    finally { setDownloading(null) }
  }
  return <div className="border-t border-gray-200 mt-3 pt-3 text-sm text-gray-700">
    {matchesReview(row, 'amount') && <p className="font-medium text-amber-800 mb-2">Invoice {row.source_totals.map(repairMoney).join(' / ')} · saved {repairMoney(row.recorded_cost)}</p>}
    <p>{row.evidence.length ? `${row.evidence.length} preserved document${row.evidence.length === 1 ? '' : 's'}` : 'No preserved documents'}</p>
    <p className="mt-1">{row.payment_status === 'unverified' ? 'Payment not verified' : 'Payment activity linked · review balances'}</p>
    <button type="button" aria-expanded={open} aria-controls={`repair-evidence-${row.legacy_id}`} onClick={() => setOpen(!open)} className="flex items-center gap-1 min-h-11 text-blue-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded">
      <svg aria-hidden="true" className={`w-4 h-4 ${open ? 'rotate-90' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m9 18 6-6-6-6" /></svg>
      Review evidence
    </button>
    {open && <div id={`repair-evidence-${row.legacy_id}`} className="space-y-3 pb-3">
      <dl className="space-y-2 tabular-nums">
        <div><dt>Recorded vendor balance</dt><dd className="font-medium">{repairMoney(row.recorded_vendor_outstanding)}</dd></div>
        <div><dt>Recorded amount owed to you</dt><dd className="font-medium">{repairMoney(row.recorded_owner_reimbursement)}</dd></div>
      </dl>
      <Link to="/finance/repairs" className="inline-flex items-center min-h-11 text-blue-700 underline focus-visible:outline focus-visible:outline-2">Record or link a repair payment</Link>
      <p>Missing payment records do not mean this repair is unpaid. Personal cash and business cash need different payment links.</p>
      {row.issues.length > 0 && <ul className="list-disc pl-4 space-y-2">{row.issues.map(issue => <li key={issue}>{reviewIssueLabels[issue] || 'Additional evidence review required.'}</li>)}</ul>}
      {row.evidence.map((doc, index) => <button key={doc.id} type="button" disabled={downloading !== null} onClick={() => download(doc.id, doc.media_type)} className="block min-h-11 text-left text-blue-700 hover:underline disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded">{downloading === doc.id ? 'Downloading…' : `Download preserved document ${index + 1}`}</button>)}
      {error && <p role="alert" className="text-red-700">Could not download the document: {error}. Try the download again.</p>}
    </div>}
  </div>
}
