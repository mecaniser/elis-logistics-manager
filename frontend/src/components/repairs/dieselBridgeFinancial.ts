import type { DieselBridgeFinancialPreview, DieselBridgeFinancialState, DieselBridgePaymentWorkspace } from '../../services/api'

export function moneyCents(value: string): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return null
  const [whole, fraction = ''] = value.split('.')
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  return Number.isSafeInteger(cents) ? cents : null
}
export function validPaymentAmount(amount: string, balance: string): boolean {
  const cents = moneyCents(amount)
  const remaining = moneyCents(balance)
  return cents !== null && remaining !== null && cents > 0 && cents <= remaining
}
export function canonicalPaymentAmount(amount: string): string | null {
  const cents = moneyCents(amount)
  if (cents === null || cents <= 0) return null
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`
}
export function paymentSummary(state: Pick<DieselBridgeFinancialState, 'payment_status' | 'recorded_paid_amount' | 'recorded_balance_due'>): string {
  if (state.payment_status === 'unconfirmed') return 'Payment history has not been confirmed. The invoice status in DBN does not establish a payment here.'
  return state.payment_status === 'paid' ? 'Paid in full from verified recorded payments.' : 'Partly paid from verified recorded payments.'
}
export function financialReviewMessage(reason: string | null | undefined): string {
  const messages: Record<string, string> = {
    date_decision_source_changed: 'The DBN source changed after the service date review. Reconfirm the date against the current invoice.',
    repair_date_changed: 'The reviewed service date differs from the imported repair. Review its booked expense and payments before applying it.',
    invoice_changed: 'The source invoice changed. The accepted cost is preserved until the correction is reviewed.',
    invoice_cancelled: 'The source invoice was cancelled. Review its existing expense and payments before applying a correction.',
    source_access_removed: 'Source access changed. Existing costs and payment records are preserved for review.',
    HISTORICAL_ATTRIBUTION_REQUIRED: 'Historical billing attribution must be approved before this invoice can be imported.',
    historical_attribution_required: 'Historical billing attribution must be approved before this invoice can be imported.',
    attribution_required: 'Historical billing attribution must be approved before this invoice can be imported.',
    cost_asset_confirmation_required: 'Confirm which vehicle this cost belongs to before importing.',
    COST_ASSET_REVIEW_REQUIRED: 'Confirm which vehicle this cost belongs to before importing.',
    cost_asset_review_required: 'Confirm which vehicle this cost belongs to before importing.',
    source_invoice_changed: 'The source invoice changed. The accepted cost is preserved until the correction is reviewed.',
    source_access_or_invoice_unavailable: 'Source access or the current invoice is unavailable. Existing costs and payment records are preserved for review.',
    source_order_unavailable: 'The repair order is no longer available from the source. Review its existing expense and payments.',
    current_finalized_invoice_required: 'A current finalized invoice is required before this repair can be imported.',
    existing_repair_invoice_review: 'An existing repair has this invoice number. Reconcile it before adding another cost.',
    date_evidence_required: 'A service completion date or supported invoice date is needed before importing.',
    DATE_EVIDENCE_REQUIRED: 'A service completion date or supported invoice date is needed before importing.',
    PAYMENT_CORRECTION_REQUIRED: 'Verified payments exist. Review their payment or refund corrections before changing or cancelling the invoice.',
    AUTHORIZED_CANCELLATION_OR_CURRENT_INVOICE_REQUIRED: 'Current invoice access or an authorized cancellation record is needed. Existing costs remain unchanged.',
    TRUCK_IDENTITY_REVIEW_REQUIRED: 'The source vehicle changed. Review the existing vehicle assignment before correcting costs.',
    truck_identity_changed: 'The source vehicle changed. Review the existing vehicle assignment before correcting costs.',
    duplicate_vin: 'More than one vehicle has this VIN. Review the vehicle assignment.',
    unmatched_vin: 'No matching vehicle was found. Review the vehicle assignment.',
  }
  const code = reason?.includes(': ') ? reason.slice(reason.lastIndexOf(': ') + 2) : reason
  return messages[code || ''] || 'Review the source invoice, vehicle assignment and existing expense before continuing.'
}
export function previewCounts(preview: DieselBridgeFinancialPreview) {
  return preview.rows.reduce((counts, row) => {
    counts[row.action] += 1
    return counts
  }, { create: 0, unchanged: 0, review_required: 0, blocked: 0 })
}
export function paymentTransactions(workspace: DieselBridgePaymentWorkspace, payer: 'business' | 'card' | 'cash') {
  const type = { business: 'bank', card: 'card', cash: 'cash' }[payer]
  const accounts = new Map(workspace.accounts.filter(a => a.account_type === type).map(a => [a.id, a]))
  return workspace.transactions.filter(t => !t.matched && Number(t.amount) < 0 && accounts.has(t.account_id)).map(t => ({ ...t, account_name: accounts.get(t.account_id)?.name || 'Reconciled account' }))
}

export function sourceReviewAllowsApply(review: { action: string; can_apply: boolean; recorded_paid_amount: string }): boolean {
  return review.can_apply && (review.action === 'no_change' || (['replace_unpaid_invoice', 'cancel_unpaid_invoice'].includes(review.action) && moneyCents(review.recorded_paid_amount) === 0))
}
