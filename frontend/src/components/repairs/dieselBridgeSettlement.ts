import type { DieselBridgeFinancialState, DieselBridgeSourcePaymentAttempt, DieselBridgeSourceSettlement } from '../../services/api'
import { moneyCents, validPaymentAmount } from './dieselBridgeFinancial'

export function sourceReceiptAmount(attempt: DieselBridgeSourcePaymentAttempt): string | null {
  const principal = moneyCents(attempt.applied_principal_amount)
  const fee = moneyCents(attempt.applied_card_fee_amount)
  const feeTax = moneyCents(attempt.applied_card_fee_tax_amount)
  const received = attempt.gross_received_amount == null ? null : moneyCents(attempt.gross_received_amount)
  const unapplied = moneyCents(attempt.unapplied_amount)
  if (attempt.state !== 'confirmed' || principal === null || fee === null || feeTax === null || received === null || unapplied !== 0) return null
  if (attempt.rail !== 'card' && (fee !== 0 || feeTax !== 0)) return null
  const total = principal + fee + feeTax
  if (!Number.isSafeInteger(total) || total <= 0 || total !== received) return null
  return `${Math.floor(total / 100)}.${String(total % 100).padStart(2, '0')}`
}
export function sourceAttemptKey(attempt: DieselBridgeSourcePaymentAttempt) {
  return JSON.stringify([attempt.attempt_id, attempt.revision])
}
export function actualSourcePaidDate(attempt: DieselBridgeSourcePaymentAttempt): string {
  const value = attempt.actual_paid_date
  if (attempt.paid_date_basis !== 'explicit_verified_date' || !value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return ''
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value ? value : ''
}
export function sourceSettlementNeedsReview(state: DieselBridgeFinancialState): boolean {
  return state.source_payment_review_required === true || state.source_settlement?.status === 'review_required'
}
export function eligibleSourceReceipts(state: DieselBridgeFinancialState): DieselBridgeSourcePaymentAttempt[] {
  const settlement = state.source_settlement
  if (state.state !== 'active' || !settlement || settlement.status !== 'available' || sourceSettlementNeedsReview(state) || moneyCents(settlement.refund_pending) !== 0 || moneyCents(settlement.unapplied_credit) !== 0) return []
  const claimed = new Set((state.source_claims || []).filter(claim => !claim.reversed).map(claim => claim.source_attempt_id))
  for (const payment of state.payments) if (!payment.reversed && payment.source_attempt_id) claimed.add(payment.source_attempt_id)
  return settlement.payments.filter(attempt => {
    const amount = sourceReceiptAmount(attempt)
    return !claimed.has(attempt.attempt_id) && /^[a-f0-9]{64}$/.test(attempt.revision) && amount !== null && validPaymentAmount(amount, state.recorded_balance_due)
  })
}
export function sourceAppliedFees(settlement: DieselBridgeSourceSettlement): { fee: string; feeTax: string } | null {
  let fee = 0
  let feeTax = 0
  for (const attempt of settlement.payments) {
    if (attempt.state !== 'confirmed') continue
    const amount = moneyCents(attempt.applied_card_fee_amount)
    const tax = moneyCents(attempt.applied_card_fee_tax_amount)
    if (amount === null || tax === null) return null
    fee += amount; feeTax += tax
    if (!Number.isSafeInteger(fee) || !Number.isSafeInteger(feeTax)) return null
  }
  const money = (value: number) => `${Math.floor(value / 100)}.${String(value % 100).padStart(2, '0')}`
  return { fee: money(fee), feeTax: money(feeTax) }
}
export const sourceRailLabel: Record<DieselBridgeSourcePaymentAttempt['rail'], string> = {
  cash: 'Cash', card: 'Card', zelle: 'Zelle', check: 'Check', ach: 'ACH', fleet_payment: 'Fleet payment',
}
