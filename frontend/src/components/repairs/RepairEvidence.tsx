import { useState } from 'react'
import RepairPaymentReview from './RepairPaymentReview'
import { financeApi, financeError } from '../../services/finance'
import { repairMoney, reviewIssueLabels, matchesReview, repairDocumentType } from './repairReview'
import type { RepairReviewRow } from './repairReview'

export default function RepairEvidence({ row, onSaved }: { row: RepairReviewRow; onSaved: () => void }) {
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
    <p className="font-semibold text-gray-900">Vendor / payee: {row.payee?.name || 'Payee not identified'}</p>
    <p className="mt-1 text-gray-600">{repairDocumentType(row)}{row.payee?.basis === 'invoice_header' ? ' · vendor from invoice' : row.payee?.basis === 'owner_confirmation' ? ' · vendor confirmed by you' : ''}</p>
    {row.payee?.basis === 'conflicting_headers' && <p className="text-amber-800">Different vendor names appear in the documents. Confirm the payee below.</p>}
    {matchesReview(row, 'amount') && <p className="font-medium text-amber-800 mb-2">Invoice {row.source_totals.map(repairMoney).join(' / ')} · saved {repairMoney(row.recorded_cost)}</p>}
    <p>{row.evidence.length ? `${row.evidence.length} preserved document${row.evidence.length === 1 ? '' : 's'}` : 'No preserved documents'}</p>
    <p className="mt-1">{row.confirmation ? (row.confirmation.stale ? 'Repair changed · review your previous answer' : `Your answer: ${{paid: 'paid in full', partial: 'partly paid', unpaid: 'not paid yet', unknown: 'not sure'}[row.confirmation.status]} · ${{cash: 'cash', zelle: 'Zelle', credit_card: 'credit card', other: 'other payment method', unknown: 'method unknown'}[row.confirmation.method]}`) : row.payment_status === 'unverified' ? 'Payment details not yet confirmed' : 'Payment activity linked'}</p>
    <button type="button" aria-expanded={open} aria-controls={`repair-evidence-${row.legacy_id}`} onClick={() => setOpen(!open)} className="flex items-center gap-1 min-h-11 text-blue-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded">
      <svg aria-hidden="true" className={`w-4 h-4 ${open ? 'rotate-90' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m9 18 6-6-6-6" /></svg>
      Invoice & payment details
    </button>
    {open && <div id={`repair-evidence-${row.legacy_id}`} className="space-y-3 pb-3">
      {row.issues.filter(issue => !['obligation_not_linked', 'payment_evidence_not_linked', 'legacy_reserve_flag_needs_funding_evidence'].includes(issue)).map(issue => <p key={issue}>{reviewIssueLabels[issue] || 'Review this repair’s details.'}</p>)}
      {row.confirmation && <p>Confirmed paid amount: {repairMoney(row.confirmation.paid_amount)} · {row.confirmation.paid_date || 'Payment date unknown'}. Funding: {{business: 'business money', personal: 'personal money', mixed: 'mixed funds', unknown: 'unknown'}[row.confirmation.source]}.</p>}
      <RepairPaymentReview key={row.confirmation?.id || row.review_snapshot} rows={[row]} onSaved={onSaved} />
      {row.evidence.map((doc, index) => <button key={doc.id} type="button" disabled={downloading !== null} onClick={() => download(doc.id, doc.media_type)} className="block min-h-11 text-left text-blue-700 hover:underline disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded">{downloading === doc.id ? 'Downloading…' : `Download preserved document ${index + 1}`}</button>)}
      {error && <p role="alert" className="text-red-700">Could not download the document: {error}. Try the download again.</p>}
    </div>}
  </div>
}
