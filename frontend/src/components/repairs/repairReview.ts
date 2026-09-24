export interface RepairReviewRow {
  legacy_id: number
  asset_name: string
  date: string | null
  description: string
  review_snapshot: string
  batch_eligible: boolean
  payee: {name: string | null; basis: string; candidates: string[]; evidence_ids: string[]}
  confirmation: {payment_account_id?: string; payment_account?: {name: string; last4: string}; payee?: string; id: string; status: string; method: string; source: string; paid_amount: string | null; paid_date: string | null; note: string; stale: boolean} | null
  recorded_cost: string | null
  source_totals: string[]
  recorded_vendor_outstanding: string | null
  recorded_owner_reimbursement: string | null
  payment_status: 'linked_activity' | 'unverified'
  evidence: { id: string; sha256: string; media_type: string; extraction_version: string }[]
  issues: string[]
}
export interface RepairReviewReport {
  tenant_id: number
  as_of: string
  rows: RepairReviewRow[]
  coverage: { records: number; with_preserved_evidence: number; with_linked_payments: number }
}
export type ReviewFilter = 'all' | 'amount' | 'documents' | 'payment' | 'treatment'
export function matchesReview(row: RepairReviewRow | undefined, filter: ReviewFilter): boolean {
  if (filter === 'all') return true
  if (!row) return false
  if (filter === 'amount') return row.issues.some(i => ['invoice_amount_difference', 'conflicting_invoice_totals'].includes(i))
  if (filter === 'documents') return row.issues.includes('missing_preserved_evidence')
  if (filter === 'payment') return row.payment_status === 'unverified' && (!row.confirmation || row.confirmation.stale || row.confirmation.status === 'unknown')
  return row.issues.some(i => ['cost_or_recovery_treatment_review', 'incurred_amount_required', 'incurred_date_required'].includes(i))
}
export const reviewIssueLabels: Record<string, string> = {
  missing_preserved_evidence: 'Attach an invoice or receipt to the evidence register.',
  incurred_date_required: 'Confirm when the repair was incurred.',
  incurred_amount_required: 'Confirm the actual charge, including whether the work was free.',
  cost_or_recovery_treatment_review: 'Review free work, recoveries or settlement deductions before recording another expense.',
  legacy_reserve_flag_needs_funding_evidence: 'The old reserve flag does not confirm that saved cash funded this repair.',
  obligation_not_linked: 'Link the existing expense before recording a payment; do not create a duplicate charge.',
  payment_evidence_not_linked: 'Confirm payment date, amount and payer. Cash receipts or Zelle/checking records can support the review.',
  invoice_amount_difference: 'The preserved invoice and saved repair amount differ. Review before correcting.',
  conflicting_invoice_totals: 'Preserved documents contain different totals. Identify the invoice that applies.',
}
export function repairMoney(value: string | null): string {
  return value === null ? 'Not established' : new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(Number(value))
}

export function repairMethod(row: RepairReviewRow | undefined): string {
  const c = row?.confirmation
  return c && !c.stale && ['paid', 'partial'].includes(c.status) ? c.method : 'unknown'
}
export function repairDocumentType(row: RepairReviewRow): string {
  return row.evidence.some(e => e.media_type === 'application/pdf') ? 'Invoice PDF' : row.evidence.length ? 'Image / other attachments' : 'No preserved document'
}
