import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTenant } from '../../contexts/tenantState'
import { dieselBridgeFinancialApi, dieselBridgeSourceReviewApi, type DieselBridgeSourceReview, type DieselBridgeFinancialState, type DieselBridgePaymentEvidence, type DieselBridgePaymentWorkspace, type DieselBridgeVerifiedPayment } from '../../services/api'
import { financeError } from '../../services/finance'
import { canonicalPaymentAmount, financialReviewMessage, paymentSummary, paymentTransactions, sourceReviewAllowsApply, validPaymentAmount } from './dieselBridgeFinancial'
import { repairMoney } from './repairReview'
import DieselBridgeReconciliationNotes from './DieselBridgeReconciliationNotes'
import DieselBridgeSettlementDetails from './DieselBridgeSettlementDetails'
import DieselBridgeReplacementReview from './DieselBridgeReplacementReview'
import { actualSourcePaidDate, eligibleSourceReceipts, sourceAttemptKey, sourceRailLabel, sourceReceiptAmount, sourceSettlementNeedsReview } from './dieselBridgeSettlement'

const EMPTY_WORKSPACE: DieselBridgePaymentWorkspace = { accounts: [], transactions: [] }
export default function DieselBridgeFinancialDetails({ repairId, state, ownerReimbursement, onSaved }: { repairId: number; state: DieselBridgeFinancialState; ownerReimbursement?: string | null; onSaved: () => void }) {
  const { currentTenant } = useTenant()
  const tenantId = currentTenant?.id
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [workspace, setWorkspace] = useState(EMPTY_WORKSPACE)
  const [evidence, setEvidence] = useState<DieselBridgePaymentEvidence[]>([])
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [optionsError, setOptionsError] = useState('')
  const [payer, setPayer] = useState<DieselBridgeVerifiedPayment['payer']>('business')
  const [amount, setAmount] = useState('')
  const [paidDate, setPaidDate] = useState('')
  const [transactionId, setTransactionId] = useState('')
  const [evidenceId, setEvidenceId] = useState('')
  const [attested, setAttested] = useState(false)
  const [note, setNote] = useState('')
  const [reverseId, setReverseId] = useState<number | null>(null)
  const [reverseDate, setReverseDate] = useState('')
  const [reverseReason, setReverseReason] = useState('')
  const [reverseConfirmed, setReverseConfirmed] = useState(false)
  const [sourceReview, setSourceReview] = useState<DieselBridgeSourceReview | null>(null)
  const [sourceNote, setSourceNote] = useState('')
  const [sourceConfirmed, setSourceConfirmed] = useState(false)
  const [sourceAttempt, setSourceAttempt] = useState('')
  const scope = `${tenantId}:${repairId}`
  const currentScope = useRef(scope)
  const mounted = useRef(true)
  const keys = useRef(new Map<string, string>())
  currentScope.current = scope
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    setOpen(false); setBusy(false); setError(''); setMessage(''); setWorkspace(EMPTY_WORKSPACE); setEvidence([])
    setAmount(''); setPaidDate(''); setTransactionId(''); setEvidenceId(''); setAttested(false); setNote(''); keys.current.clear()
    setReverseId(null); setReverseDate(''); setReverseReason(''); setReverseConfirmed(false)
    setSourceReview(null); setSourceNote(''); setSourceConfirmed(false); setSourceAttempt('')
  }, [scope])
  useEffect(() => {
    if (state.state !== 'active' || sourceSettlementNeedsReview(state)) setOpen(false)
  }, [state])
  useEffect(() => {
    let active = true
    if (!open || !tenantId) return
    setOptionsLoading(true); setOptionsError('')
    const today = localToday()
    Promise.all([dieselBridgeFinancialApi.paymentOptions(tenantId, today), dieselBridgeFinancialApi.paymentEvidence(tenantId)]).then(([choices, documents]) => {
      if (!active) return
      setWorkspace(choices.data)
      const superseded = new Set(documents.map(doc => doc.supersedes_id).filter(Boolean))
      setEvidence(documents.filter(doc => !superseded.has(doc.id) && doc.extraction_version === 'elis-evidence-v1'))
    }).catch(e => { if (active) setOptionsError(financeError(e)) }).finally(() => { if (active) setOptionsLoading(false) })
    return () => { active = false }
  }, [open, tenantId])
  const current = (requested: string) => mounted.current && currentScope.current === requested
  const idempotencyKey = (fingerprint: string) => {
    if (!keys.current.has(fingerprint)) keys.current.set(fingerprint, crypto.randomUUID())
    return keys.current.get(fingerprint)!
  }
  async function run(action: (requested: string) => Promise<void>) {
    const requested = scope
    setBusy(true); setError(''); setMessage('')
    try { await action(requested) } catch (e) { if (current(requested)) setError(financeError(e)) }
    finally { if (current(requested)) setBusy(false) }
  }
  const receipts = eligibleSourceReceipts(state)
  const selectedReceipt = receipts.find(attempt => sourceAttemptKey(attempt) === sourceAttempt)
  const paymentBlocked = state.state !== 'active' || sourceSettlementNeedsReview(state)
  const transactions = payer === 'owner' ? [] : paymentTransactions(workspace, payer)
  useEffect(() => {
    if (sourceAttempt && !selectedReceipt) {
      setSourceAttempt(''); setAmount(''); setPaidDate(''); setTransactionId(''); setEvidenceId(''); setAttested(false)
      setError('The selected DBN payment record changed or is no longer available. Review it and choose payment evidence again.')
    }
  }, [sourceAttempt, selectedReceipt])
  const control = 'mt-1 block min-h-11 w-full rounded border border-gray-300 bg-white px-3 text-base focus-visible:outline-blue-600'
  const button = 'min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600'
  function choosePayer(next: DieselBridgeVerifiedPayment['payer']) {
    setPayer(next); setTransactionId(''); setPaidDate(next === 'owner' && selectedReceipt ? actualSourcePaidDate(selectedReceipt) : ''); setEvidenceId(''); setAttested(false)
  }
  function chooseSourceAttempt(key: string) {
    const attempt = receipts.find(item => sourceAttemptKey(item) === key)
    setSourceAttempt(key); setAmount(attempt ? sourceReceiptAmount(attempt) || '' : '')
    setTransactionId(''); setEvidenceId(''); setAttested(false)
    setPaidDate(attempt && payer === 'owner' ? actualSourcePaidDate(attempt) : '')
  }
  function chooseTransaction(id: string) {
    setTransactionId(id)
    const transaction = transactions.find(t => t.id === id)
    setPaidDate(transaction?.date || '')
  }
  async function save(event: FormEvent) {
    event.preventDefault()
    if (!tenantId || paymentBlocked || (sourceAttempt && !selectedReceipt) || !validPaymentAmount(amount, state.recorded_balance_due)) return
    const canonicalAmount = canonicalPaymentAmount(amount)
    if (!canonicalAmount) return
    const body: DieselBridgeVerifiedPayment = { expected_revision: state.revision, amount: canonicalAmount, paid_date: paidDate, payer, note: note.trim(),
      ...(payer === 'owner' ? { evidence_id: evidenceId, owner_payment_confirmed: true } : { transaction_id: transactionId }),
      ...(selectedReceipt ? { source_attempt_id: selectedReceipt.attempt_id, source_attempt_revision: selectedReceipt.revision } : {}) }
    await run(async requested => {
      await dieselBridgeFinancialApi.payment(tenantId, repairId, body, idempotencyKey(`payment:${JSON.stringify(body)}`))
      if (!current(requested)) return
      setAmount(''); setTransactionId(''); setPaidDate(''); setAttested(false); setEvidenceId(''); setNote(''); setSourceAttempt('')
      setOpen(false); setMessage('Verified payment recorded. The reserve withdrawal uses this amount and payment date.'); onSaved()
    })
  }
  async function reverse(event: FormEvent) {
    event.preventDefault()
    if (!tenantId || reverseId === null || !reverseConfirmed) return
    const body = { reversal_date: reverseDate, reason: reverseReason.trim(), expected_revision: state.revision }
    const paymentId = reverseId
    await run(async requested => {
      await dieselBridgeFinancialApi.reverse(tenantId, repairId, paymentId, body, idempotencyKey(`reverse:${paymentId}:${JSON.stringify(body)}`))
      if (!current(requested)) return
      setReverseId(null); setReverseReason(''); setReverseConfirmed(false)
      setMessage('Payment correction recorded and its reserve withdrawal reversed. Original records were retained.'); onSaved()
    })
  }
  async function previewSourceReview() {
    if (!tenantId) return
    await run(async requested => {
      const response = await dieselBridgeSourceReviewApi.preview(tenantId, repairId, state.revision)
      if (!current(requested)) return
      setSourceReview(response.data); setSourceNote(''); setSourceConfirmed(false)
    })
  }
  async function applySourceReview(event: FormEvent) {
    event.preventDefault()
    if (!tenantId || !sourceReview || !sourceReviewAllowsApply(sourceReview) || !sourceConfirmed) return
    const body = { expected_revision: state.revision, expected_review_digest: sourceReview.review_digest, note: sourceNote.trim() }
    await run(async requested => {
      await dieselBridgeSourceReviewApi.apply(tenantId, repairId, body, idempotencyKey(`source-review:${JSON.stringify(body)}`))
      if (!current(requested)) return
      setSourceReview(null); setSourceNote(''); setSourceConfirmed(false)
      setMessage('Source correction recorded. Original invoice and accounting references were retained.'); onSaved()
    })
  }
  return <div className="mt-3 border-t border-gray-200 pt-3 text-sm text-gray-700" aria-label="DBN invoice and verified payments" aria-busy={busy}>
    <p className="font-semibold text-gray-900">DBN invoice {state.invoice_number}</p>
    <p className="mt-1 text-gray-600">{state.order_number ? `Repair order ${state.order_number}` : 'Linked to its source repair order'}</p>
    {state.equipment_allocation && <p className="mt-1 text-gray-600">{state.equipment_allocation.work_equipment_type === 'trailer' ? 'Trailer work' : 'Truck work'}{state.equipment_allocation.interim_unit_allocation ? ' · temporarily assigned to this truck unit; trailer identity unresolved' : ' · equipment reviewed'}. {state.equipment_allocation.reason}</p>}
    {state.state !== 'active' && <p className="mt-2 rounded bg-amber-50 p-2 font-medium text-amber-900">{financialReviewMessage(state.review_reason)}</p>}
    <DieselBridgeSettlementDetails state={state} />
    {tenantId && <DieselBridgeReplacementReview key={`${tenantId}:${repairId}:${state.revision}`} tenantId={tenantId} repairId={repairId} state={state} onSaved={onSaved} />}
    <DieselBridgeReconciliationNotes key={`${tenantId}:${repairId}:${state.repair_order_id}`} repairId={repairId} state={state} onSaved={onSaved} />
    <dl className="mt-3 space-y-1">
      <div className="flex flex-wrap justify-between gap-2"><dt>Verified payments recorded</dt><dd className="font-medium">{repairMoney(state.recorded_paid_amount)}</dd></div>
      <div className="flex flex-wrap justify-between gap-2"><dt>Recorded balance due</dt><dd className="font-medium">{repairMoney(state.recorded_balance_due)}</dd></div>
    </dl>
    {ownerReimbursement && Number(ownerReimbursement) > 0 && <p className="mt-2 font-medium text-emerald-800">Recorded business reimbursement owed to you: {repairMoney(ownerReimbursement)}</p>}
    <p className="mt-2 text-xs text-gray-600">{paymentSummary(state)}</p>
    {state.payment_history_confirmed !== true && <p className="mt-1 text-xs text-gray-600">Balances reflect payments recorded here. Reconcile any earlier payments before adding another.</p>}
    <p className="mt-1 text-xs text-gray-600">Only verified recorded payments withdraw from reserve; invoice cost is recorded once.</p>
    <div className="mt-3 flex flex-wrap gap-2">
      {state.state !== 'access_removed' && <button type="button" className={`${button} text-blue-700`} disabled={busy || !tenantId} onClick={() => run(async requested => {
        const response = await dieselBridgeFinancialApi.pdf(tenantId!, repairId)
        if (!current(requested)) return
        const url = URL.createObjectURL(response.data)
        const link = document.createElement('a'); link.href = url; link.download = `DBN-${state.invoice_number.replace(/[^a-zA-Z0-9_-]/g, '-')}.pdf`; link.click()
        setTimeout(() => URL.revokeObjectURL(url), 60000)
      })}>Current DBN invoice PDF</button>}
      <button type="button" aria-expanded={open} className={`${button} text-blue-700`} disabled={busy || paymentBlocked || !validPaymentAmount('0.01', state.recorded_balance_due)} onClick={() => { setOpen(!open); setError('') }}>Record verified payment</button>
    </div>
    <p className="mt-2 text-xs text-gray-600">The current DBN invoice PDF may include quoted conditional card fees. Use the settlement and actual charged fees above to reconcile the booked repair cost. This is a current source copy.</p>
    {state.state !== 'active' && <p className="mt-2 text-xs text-amber-900">The current DBN PDF may differ from the accepted repair cost. Review the proposed correction before changing saved costs.</p>}
    {state.state !== 'active' && <button type="button" className={`${button} mt-2 text-blue-700`} disabled={busy} onClick={previewSourceReview}>Review source change</button>}
    {sourceReview && <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3">
      <p className="font-semibold">Source invoice correction preview</p>
      <dl className="mt-2 space-y-2">
        <div><dt className="font-medium">Accepted invoice</dt><dd>{sourceReview.before.invoice_number} · {repairMoney(sourceReview.before.cost)} · {sourceReview.before.repair_date || 'Date unavailable'}{sourceReview.before.description && <p>{sourceReview.before.description}</p>}</dd></div>
        <div><dt className="font-medium">Proposed correction</dt><dd>{sourceReview.action === 'no_change' ? 'The source matches the accepted invoice. Confirming restores its reviewed status without changing costs or payments.' : sourceReview.action === 'cancel_unpaid_invoice' ? 'Archive this cancelled repair and reverse its unpaid expense. Original records and evidence will be retained.' : sourceReview.after ? <>{sourceReview.after.invoice_number} · {repairMoney(sourceReview.after.cost)} · {sourceReview.after.repair_date || 'Date needs review'}{sourceReview.after.description && <p>{sourceReview.after.description}</p>}</> : 'No financial correction can be applied from this source information.'}</dd></div>
      </dl>
      {sourceReview.candidate_pdf_url && <button type="button" className={`${button} mt-2 bg-white text-blue-700`} disabled={busy || !tenantId} onClick={() => run(async requested => {
        const response = await dieselBridgeSourceReviewApi.pdf(tenantId!, repairId)
        if (!current(requested)) return
        const url = URL.createObjectURL(response.data)
        const link = document.createElement('a'); link.href = url; link.download = `DBN-proposed-invoice-${repairId}.pdf`; link.click()
        setTimeout(() => URL.revokeObjectURL(url), 60000)
      })}>Proposed invoice PDF</button>}
      <p className="mt-2 text-xs">Verified payments recorded: {repairMoney(sourceReview.recorded_paid_amount)}. Paid invoices need payment/refund reconciliation before their costs can be changed or cancelled.</p>
      {sourceReview.blockers.map(reason => <p key={reason} className="mt-2 text-amber-900">{financialReviewMessage(reason)}</p>)}
      {sourceReviewAllowsApply(sourceReview) && <form onSubmit={applySourceReview} className="mt-3 space-y-2">
        <label className="block">Review note<textarea className={`${control} py-2`} required minLength={3} maxLength={2000} value={sourceNote} disabled={busy} onChange={e => setSourceNote(e.target.value)} /></label>
        <label className="flex min-h-11 items-start gap-2"><input className="mt-1" type="checkbox" required checked={sourceConfirmed} disabled={busy} onChange={e => setSourceConfirmed(e.target.checked)} /><span>I reviewed the source invoice and this correction to the saved repair cost and accounting records.</span></label>
        <button type="submit" className={`${button} bg-white text-blue-700`} disabled={busy || !sourceConfirmed || sourceNote.trim().length < 3}>{sourceReview.action === 'no_change' ? 'Confirm reviewed source status' : 'Apply reviewed source correction'}</button>
      </form>}
      <button type="button" className={`${button} mt-2`} disabled={busy} onClick={() => setSourceReview(null)}>Close correction preview</button>
    </div>}
    {open && <form onSubmit={save} className="mt-3 space-y-3 rounded border border-gray-200 bg-gray-50 p-3">
      <p>Record an actual payment already made. This records its accounting and reserve effects; it does not send money.</p>
      {state.source_settlement && <>
        <label className="block">DBN confirmed payment record (optional)<select className={control} value={sourceAttempt} disabled={busy} onChange={event => chooseSourceAttempt(event.target.value)}><option value="">No DBN attempt selected — reconcile independently</option>{receipts.map(attempt => <option key={sourceAttemptKey(attempt)} value={sourceAttemptKey(attempt)}>{sourceRailLabel[attempt.rail]} · {repairMoney(sourceReceiptAmount(attempt)!)} · {actualSourcePaidDate(attempt) || 'Actual date unknown'} · {attempt.attempt_id}</option>)}</select></label>
        {selectedReceipt ? <p className="text-xs text-gray-600">The full DBN receipt is {repairMoney(sourceReceiptAmount(selectedReceipt)!)}: applied principal plus actual card fee and fee tax. Partial allocations of one source receipt are not supported. Verify its actual date and funding below; DBN confirmation time is not a payment date.</p> : <p className="text-xs text-amber-900">Before recording an independent payment, check the DBN attempts and existing EDG payments to avoid recording the same receipt twice. Pending, refunded, reversed, unapplied or already linked source attempts cannot be selected.</p>}
      </>}
      {optionsLoading && <p>Loading reconciled transactions and payment evidence…</p>}
      {optionsError && <p role="alert" className="text-red-700">Payment choices could not be loaded: {optionsError}. Close this form and reopen it to retry.</p>}
      <label className="block">Funding source<select className={control} value={payer} disabled={busy} onChange={e => choosePayer(e.target.value as DieselBridgeVerifiedPayment['payer'])}><option value="business">Business bank account</option><option value="card">Business credit card</option><option value="cash">Business cash account</option><option value="owner">Personal funds</option></select></label>
      {payer !== 'owner' ? <label className="block">Reconciled outgoing transaction<select className={control} required value={transactionId} disabled={busy || optionsLoading || !!optionsError} onChange={e => chooseTransaction(e.target.value)}><option value="">Choose the payment transaction…</option>{transactions.map(t => <option key={t.id} value={t.id}>{t.date} · {t.account_name} · {repairMoney(String(Math.abs(Number(t.amount))))}{t.description ? ` · ${t.description}` : ''}</option>)}</select>{!optionsLoading && !transactions.length && <span className="mt-1 block text-xs">No unmatched outgoing transactions of this type. Reconcile the payment in Accounting first.</span>}</label> : <>
        <label className="block">Preserved payment receipt<select className={control} required value={evidenceId} disabled={busy || optionsLoading || !!optionsError} onChange={e => setEvidenceId(e.target.value)}><option value="">Choose evidence of the actual personal payment…</option>{evidence.map(doc => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}</select></label>
        <p className="text-xs">Use a receipt or payment record, not just the repair invoice. Supporting documents can be uploaded in Accounting.</p>
        <label className="flex min-h-11 items-start gap-2"><input type="checkbox" required checked={attested} disabled={busy} onChange={e => setAttested(e.target.checked)} className="mt-1" /><span>I confirm this was an actual personal payment and the selected document supports its amount and date.</span></label>
      </>}
      <label className="block">Payment explanation<textarea className={`${control} py-2`} required minLength={3} maxLength={2000} value={note} disabled={busy} onChange={e => setNote(e.target.value)} /></label>
      <label className="block">Amount paid on this occasion<input className={control} inputMode="decimal" required value={amount} disabled={busy} readOnly={!!selectedReceipt} onChange={e => setAmount(e.target.value)} placeholder="0.00" /></label>
      {amount && !validPaymentAmount(amount, state.recorded_balance_due) && <p className="text-red-700">Enter a positive amount no greater than the recorded balance due, with at most two decimal places.</p>}
      <label className="block">Actual payment date<input className={control} type="date" required max={localToday()} value={paidDate} disabled={busy || payer !== 'owner'} onChange={e => setPaidDate(e.target.value)} /></label>
      <p className="text-xs">A partial payment reduces the recorded balance due by its amount. The server checks transaction allocation and remaining balance again before saving.</p>
      <button type="submit" className={`${button} bg-white text-blue-700`} disabled={busy || paymentBlocked || (!!sourceAttempt && !selectedReceipt) || optionsLoading || !!optionsError || !paidDate || note.trim().length < 3 || !validPaymentAmount(amount, state.recorded_balance_due) || (payer === 'owner' ? !attested || !evidenceId || note.trim().length < 3 : !transactionId)}>Record payment</button>
      <button type="button" className={`${button} ml-2`} disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
    </form>}
    {!!state.payments.length && <details className="mt-3"><summary className="min-h-11 cursor-pointer py-2 text-blue-700">Verified payment records ({state.payments.length})</summary>
      <ul className="space-y-2">{state.payments.map(payment => <li key={payment.id} className="rounded border border-gray-200 p-2">
        <p>{payment.paid_date} · {repairMoney(payment.amount)} · {{ business: 'business bank', owner: 'personal funds', card: 'business card', cash: 'business cash' }[payment.payer]}{payment.reversed ? ' · reversed' : ''}</p>
        {payment.source_attempt_id && <p className="mt-1 break-all text-xs text-gray-600">Linked DBN payment attempt: {payment.source_attempt_id}</p>}
        {!payment.reversed && <button type="button" className={`${button} mt-2 text-blue-700`} disabled={busy} onClick={() => { setReverseId(reverseId === payment.id ? null : payment.id); setReverseDate(''); setReverseReason(''); setReverseConfirmed(false) }}>Review payment correction</button>}
        {reverseId === payment.id && <form onSubmit={reverse} className="mt-3 space-y-2">
          <p>The original payment and evidence will be retained. This appends a correction and reverses its reserve withdrawal.</p>
          <label className="block">Correction date<input className={control} required type="date" min={payment.paid_date} max={localToday()} value={reverseDate} disabled={busy} onChange={e => setReverseDate(e.target.value)} /></label>
          <label className="block">Reason<textarea className={`${control} py-2`} required minLength={3} maxLength={2000} value={reverseReason} disabled={busy} onChange={e => setReverseReason(e.target.value)} /></label>
          <label className="flex min-h-11 items-start gap-2"><input className="mt-1" type="checkbox" required checked={reverseConfirmed} disabled={busy} onChange={e => setReverseConfirmed(e.target.checked)} /><span>I reviewed this correction to the recorded payment and reserve withdrawal.</span></label>
          <button className={`${button} bg-white text-blue-700`} type="submit" disabled={busy || !reverseConfirmed || !reverseDate || reverseReason.trim().length < 3}>Record payment correction</button>
          <button className={`${button} ml-2`} type="button" disabled={busy} onClick={() => setReverseId(null)}>Cancel</button>
        </form>}
      </li>)}</ul>
    </details>}
    {error && <p role="alert" className="mt-3 text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-gray-700">{message}</p>}
  </div>
}
function localToday() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
